"""
Hajimi King - 数据库版本
使用 SQLite 数据库替代文本文件
"""
import os
import random
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any

from common.Logger import logger

sys.path.append('../')
from common.config import config
from utils.github_client import GitHubClient
from utils.db_manager import db_manager
from utils.file_manager import file_manager  # 保留用于加载 queries
from utils.sync_utils import sync_utils
from web.database import init_db

# 初始化数据库
init_db()

# 创建GitHub工具实例
github_utils = GitHubClient.create_instance(config.GITHUB_TOKENS)

# 统计信息
skip_stats = {
    "sha_duplicate": 0,
    "age_filter": 0,
    "doc_filter": 0
}


def should_skip_item(item: Dict[str, Any]) -> tuple[bool, str]:
    """
    检查是否应该跳过处理此item

    Returns:
        tuple: (should_skip, reason)
    """
    # 检查SHA是否已扫描（使用数据库）
    file_sha = item.get("sha")
    if file_sha and db_manager.is_file_scanned(file_sha):
        skip_stats["sha_duplicate"] += 1
        return True, "sha_duplicate"

    # 检查仓库年龄
    repo_pushed_at = item["repository"].get("pushed_at")
    if repo_pushed_at:
        try:
            repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
            if repo_pushed_dt < datetime.utcnow() - timedelta(days=config.DATE_RANGE_DAYS):
                skip_stats["age_filter"] += 1
                return True, "age_filter"
        except Exception as e:
            logger.warning(f"Failed to parse repo_pushed_at: {e}")

    # 检查文档和示例文件
    lowercase_path = item["path"].lower()
    if any(token in lowercase_path for token in config.FILE_PATH_BLACKLIST):
        skip_stats["doc_filter"] += 1
        return True, "doc_filter"

    return False, ""


def process_item(item: Dict[str, Any]) -> tuple:
    """
    处理单个GitHub搜索结果item

    Returns:
        tuple: (valid_keys_count, rate_limited_keys_count)
    """
    delay = random.uniform(1, 5)
    file_url = item["html_url"]
    repo_name = item["repository"]["full_name"]
    file_path = item["path"]
    file_sha = item.get("sha")

    time.sleep(delay)

    content = github_utils.get_file_content(item)
    if not content:
        logger.warning(f"⚠️ Failed to fetch content for file: {file_url}")
        return 0, 0

    # 使用基于配置的多供应商密钥提取
    from app.providers.config_key_extractor import config_key_extractor
    all_keys = config_key_extractor.extract_all_keys(content)

    if not all_keys:
        # 标记文件为已扫描（即使没有找到密钥）
        if file_sha:
            try:
                repo_pushed_at_str = item["repository"].get("pushed_at")
                repo_pushed_at = datetime.strptime(repo_pushed_at_str, "%Y-%m-%dT%H:%M:%SZ") if repo_pushed_at_str else None

                db_manager.mark_file_scanned(
                    file_sha=file_sha,
                    repo=repo_name,
                    file_path=file_path,
                    file_url=file_url,
                    keys_found=0,
                    valid_keys_count=0,
                    repo_pushed_at=repo_pushed_at
                )
            except Exception as e:
                logger.error(f"Failed to mark file as scanned: {e}")

        return 0, 0

    total_valid_keys = 0
    total_rate_limited_keys = 0
    total_keys_found = 0

    # 处理每个供应商的密钥
    for provider_name, keys in all_keys.items():
        if not keys:
            continue

        logger.info(f"🔑 Found {len(keys)} {provider_name} suspected key(s), validating...")

        # 过滤占位符密钥
        filtered_keys = []
        for key in keys:
            context_index = content.find(key)
            if context_index != -1:
                snippet = content[context_index:context_index + 45]
                if "..." in snippet or "YOUR_" in snippet.upper():
                    continue
            filtered_keys.append(key)

        # 去重处理
        keys = list(set(filtered_keys))

        if not keys:
            continue

        valid_keys = []
        rate_limited_keys = []
        invalid_keys = []

        # 获取供应商实例并验证密钥
        try:
            from app.providers.config_based_factory import ConfigBasedAIProviderFactory
            provider = ConfigBasedAIProviderFactory.get_provider_by_name(provider_name)

            if not provider:
                logger.warning(f"❌ Provider {provider_name} not found in configuration")
                continue

            for key in keys:
                total_keys_found += 1

                validation_result = provider.validate_key(key)

                if validation_result and "ok" in validation_result:
                    valid_keys.append(key)
                    logger.info(f"✅ VALID {provider_name.upper()}: {key}")

                    # 保存到数据库
                    group_name = config_key_extractor.get_gpt_load_group_name(provider_name)
                    db_manager.save_api_key(
                        api_key=key,
                        provider=provider_name,
                        status='valid',
                        source_repo=repo_name,
                        source_file_path=file_path,
                        source_file_url=file_url,
                        source_file_sha=file_sha,
                        gpt_load_group_name=group_name,
                        metadata={'validation_result': validation_result}
                    )

                elif "rate_limited" in validation_result:
                    rate_limited_keys.append(key)
                    logger.warning(f"⚠️ RATE LIMITED {provider_name.upper()}: {key}")

                    # 保存到数据库
                    group_name = config_key_extractor.get_gpt_load_group_name(provider_name)
                    db_manager.save_api_key(
                        api_key=key,
                        provider=provider_name,
                        status='rate_limited',
                        source_repo=repo_name,
                        source_file_path=file_path,
                        source_file_url=file_url,
                        source_file_sha=file_sha,
                        gpt_load_group_name=group_name,
                        metadata={'validation_result': validation_result}
                    )

                else:
                    invalid_keys.append(key)
                    logger.info(f"❌ INVALID {provider_name.upper()}: {key}, result: {validation_result}")

                    # 保存到数据库
                    db_manager.save_api_key(
                        api_key=key,
                        provider=provider_name,
                        status='invalid',
                        source_repo=repo_name,
                        source_file_path=file_path,
                        source_file_url=file_url,
                        source_file_sha=file_sha,
                        metadata={'validation_result': validation_result}
                    )

        except Exception as e:
            logger.error(f"❌ Error validating {provider_name} keys: {e}")
            continue

        # 添加有效密钥到同步队列
        if valid_keys:
            try:
                group_name = config_key_extractor.get_gpt_load_group_name(provider_name)
                sync_utils.add_keys_to_queue(valid_keys, provider_name, group_name)
                logger.info(f"📥 Added {len(valid_keys)} {provider_name} key(s) to sync queues (Group: {group_name})")
            except Exception as e:
                logger.error(f"📥 Error adding {provider_name} keys to sync queues: {e}")

        total_valid_keys += len(valid_keys)
        total_rate_limited_keys += len(rate_limited_keys)

    # 标记文件为已扫描
    if file_sha:
        try:
            repo_pushed_at_str = item["repository"].get("pushed_at")
            repo_pushed_at = datetime.strptime(repo_pushed_at_str, "%Y-%m-%dT%H:%M:%SZ") if repo_pushed_at_str else None

            db_manager.mark_file_scanned(
                file_sha=file_sha,
                repo=repo_name,
                file_path=file_path,
                file_url=file_url,
                keys_found=total_keys_found,
                valid_keys_count=total_valid_keys,
                repo_pushed_at=repo_pushed_at
            )
        except Exception as e:
            logger.error(f"Failed to mark file as scanned: {e}")

    return total_valid_keys, total_rate_limited_keys


def print_skip_stats():
    """打印跳过统计信息"""
    total_skipped = sum(skip_stats.values())
    if total_skipped > 0:
        logger.info(f"📊 Skipped {total_skipped} items - Duplicate: {skip_stats['sha_duplicate']}, Age: {skip_stats['age_filter']}, Docs: {skip_stats['doc_filter']}")


def reset_skip_stats():
    """重置跳过统计"""
    global skip_stats
    skip_stats = {"sha_duplicate": 0, "age_filter": 0, "doc_filter": 0}


def main():
    start_time = datetime.now()

    # 打印系统启动信息
    logger.info("=" * 60)
    logger.info("🚀 HAJIMI KING STARTING (Database Mode)")
    logger.info("=" * 60)
    logger.info(f"⏰ Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 检查配置
    if not config.check():
        logger.info("❌ Config check failed. Exiting...")
        sys.exit(1)

    # 2. 显示数据库状态
    stats = db_manager.get_stats_summary()
    logger.info("📊 DATABASE STATUS:")
    logger.info(f"   Total keys: {stats['total_keys']}")
    logger.info(f"   Valid keys: {stats['valid_keys']}")
    logger.info(f"   Rate limited: {stats['rate_limited_keys']}")
    logger.info(f"   Invalid: {stats['invalid_keys']}")
    logger.info(f"   Today's keys: {stats['today_keys']}")

    # 3. 显示同步状态
    if sync_utils.balancer_enabled or config.parse_bool(config.GPT_LOAD_SYNC_ENABLED):
        logger.info("🔗 SYNC STATUS:")
        if stats['pending_balancer_sync'] > 0:
            logger.info(f"   Pending Balancer sync: {stats['pending_balancer_sync']}")
        if stats['pending_gpt_load_sync'] > 0:
            logger.info(f"   Pending GPT Load sync: {stats['pending_gpt_load_sync']}")

    # 4. 显示系统信息
    search_queries = file_manager.get_search_queries()

    # 如果没有自定义查询，从供应商的 key_patterns 自动生成
    if not search_queries:
        logger.info("📝 No custom queries found, generating from provider patterns...")
        search_queries = []
        providers = config.AI_PROVIDERS_CONFIG
        languages = ['python', 'javascript', 'go', 'java', 'typescript']

        for provider in providers:
            patterns = provider.get('key_patterns', [])
            for pattern in patterns:
                # 从正则提取关键前缀（如 AIzaSy, sk-proj）
                if pattern.startswith('AIzaSy'):
                    prefix = 'AIzaSy'
                elif pattern.startswith('sk-'):
                    prefix = 'sk-'
                else:
                    # 尝试提取前6个非正则字符
                    import re
                    match = re.match(r'^([A-Za-z0-9\-_]{3,10})', pattern)
                    if match:
                        prefix = match.group(1)
                    else:
                        continue

                # 为每个语言生成查询
                for lang in languages:
                    search_queries.append(f'{prefix} language:{lang}')

        logger.info(f"✅ Generated {len(search_queries)} queries from {len(providers)} provider(s)")

    logger.info("📋 SYSTEM INFORMATION:")
    logger.info(f"🔑 GitHub tokens: {len(config.GITHUB_TOKENS)} configured")
    logger.info(f"🔍 Search queries: {len(search_queries)} loaded")
    logger.info(f"📅 Date filter: {config.DATE_RANGE_DAYS} days")
    if config.PROXY_LIST:
        logger.info(f"🌐 Proxy: {len(config.PROXY_LIST)} proxies configured")

    logger.info("✅ System ready - Starting mining")
    logger.info("=" * 60)

    total_keys_found = 0
    total_rate_limited_keys = 0
    loop_count = 0

    while True:
        try:
            loop_count += 1
            logger.info(f"🔄 Loop #{loop_count} - {datetime.now().strftime('%H:%M:%S')}")

            query_count = 0
            loop_processed_files = 0
            reset_skip_stats()

            for i, q in enumerate(search_queries, 1):
                res = github_utils.search_for_keys(q)

                if res and "items" in res:
                    items = res["items"]
                    if items:
                        query_valid_keys = 0
                        query_rate_limited_keys = 0
                        query_processed = 0

                        for item_index, item in enumerate(items, 1):
                            # 每20个item显示进度
                            if item_index % 20 == 0:
                                logger.info(
                                    f"📈 Progress: {item_index}/{len(items)} | query: {q} | current valid: {query_valid_keys} | total valid: {total_keys_found}")

                            # 检查是否应该跳过此item
                            should_skip, skip_reason = should_skip_item(item)
                            if should_skip:
                                continue

                            # 处理单个item
                            valid_count, rate_limited_count = process_item(item)

                            query_valid_keys += valid_count
                            query_rate_limited_keys += rate_limited_count
                            query_processed += 1
                            loop_processed_files += 1

                        total_keys_found += query_valid_keys
                        total_rate_limited_keys += query_rate_limited_keys

                        if query_processed > 0:
                            logger.info(f"✅ Query {i}/{len(search_queries)} complete - Processed: {query_processed}, Valid: +{query_valid_keys}, Rate limited: +{query_rate_limited_keys}")
                        else:
                            logger.info(f"⏭️ Query {i}/{len(search_queries)} complete - All items skipped")

                        print_skip_stats()
                    else:
                        logger.info(f"📭 Query {i}/{len(search_queries)} - No items found")
                else:
                    logger.warning(f"❌ Query {i}/{len(search_queries)} failed")

                query_count += 1

                if query_count % 5 == 0:
                    logger.info(f"⏸️ Processed {query_count} queries, taking a break...")
                    time.sleep(1)

            logger.info(f"🏁 Loop #{loop_count} complete - Processed {loop_processed_files} files | Total valid: {total_keys_found} | Total rate limited: {total_rate_limited_keys}")

            # 休眠指定分钟数（从配置读取）
            sleep_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
            logger.info(f"💤 Sleeping for {sleep_minutes} minutes...")
            time.sleep(sleep_minutes * 60)

        except KeyboardInterrupt:
            logger.info("⛔ Interrupted by user")
            logger.info(f"📊 Final stats - Valid keys: {total_keys_found}, Rate limited: {total_rate_limited_keys}")
            logger.info("🔚 Shutting down sync utils...")
            sync_utils.shutdown()
            break
        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}")
            traceback.print_exc()
            logger.info("🔄 Waiting 60s before retry...")
            time.sleep(60)
            continue


if __name__ == "__main__":
    main()
