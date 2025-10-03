import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

import requests

from common.Logger import logger
from common.config import config
from utils.file_manager import file_manager


class SyncUtils:
    """同步工具类，负责异步发送keys到外部应用"""

    def __init__(self):
        """初始化同步工具"""
        # Gemini Balancer 配置
        self.balancer_url = config.GEMINI_BALANCER_URL.rstrip('/') if config.GEMINI_BALANCER_URL else ""
        self.balancer_auth = config.GEMINI_BALANCER_AUTH
        self.balancer_sync_enabled = config.parse_bool(config.GEMINI_BALANCER_SYNC_ENABLED)
        self.balancer_enabled = bool(self.balancer_url and self.balancer_auth and self.balancer_sync_enabled)

        # GPT Load Balancer 配置
        self.gpt_load_url = config.GPT_LOAD_URL.rstrip('/') if config.GPT_LOAD_URL else ""
        self.gpt_load_auth = config.GPT_LOAD_AUTH
        self.gpt_load_sync_enabled = config.parse_bool(config.GPT_LOAD_SYNC_ENABLED)
        self.gpt_load_enabled = bool(self.gpt_load_url and self.gpt_load_auth and self.gpt_load_sync_enabled)
        
        # 从AI_PROVIDERS_CONFIG获取group names
        self.gpt_load_group_names = []
        self.provider_to_group_map = {}
        if self.gpt_load_enabled:
            for provider_config in config.AI_PROVIDERS_CONFIG:
                group_name = provider_config.get('gpt_load_group_name', '').strip()
                if group_name:
                    self.gpt_load_group_names.append(group_name)
                    provider_name = provider_config.get('name', '')
                    if provider_name:
                        self.provider_to_group_map[provider_name] = group_name
            
            # 去重
            self.gpt_load_group_names = list(set(self.gpt_load_group_names))

        # 创建线程池用于异步执行
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="SyncUtils")
        self.saving_checkpoint = False

        # 周期性发送控制
        self.batch_interval = 60
        self.batch_timer = None
        self.shutdown_flag = False

        # GPT Load Balancer group ID 缓存 (15分钟缓存)
        self.group_id_cache: Dict[str, int] = {}
        self.group_id_cache_time: Dict[str, float] = {}
        self.group_id_cache_ttl = 15 * 60  # 15分钟

        if not self.balancer_enabled:
            logger.warning("🚫 Gemini Balancer sync disabled - URL or AUTH not configured")
        else:
            logger.info(f"🔗 Gemini Balancer enabled - URL: {self.balancer_url}")

        if not self.gpt_load_enabled:
            logger.warning("🚫 GPT Load Balancer sync disabled - URL, AUTH not configured or sync disabled")
        else:
            logger.info(f"🔗 GPT Load Balancer enabled - URL: {self.gpt_load_url}, Groups: {', '.join(self.gpt_load_group_names)}")

        # 启动周期性发送线程
        self._start_batch_sender()

    def add_keys_to_queue(self, keys: List[str], provider_name: str = "", group_name: str = ""):
        """
        将keys同时添加到balancer和GPT load的发送队列
        
        Args:
            keys: API keys列表
            provider_name: 供应商名称（用于日志记录）
            group_name: GPT Load Group名称（如果提供，将覆盖默认配置）
        """
        if not keys:
            return

        # Acquire lock for checkpoint saving
        while self.saving_checkpoint:
            logger.info(f"📥 Checkpoint is currently being saved, waiting before adding {len(keys)} {provider_name} key(s) to queues...")
            time.sleep(1)  # Small delay to prevent busy-waiting

        self.saving_checkpoint = True  # Acquire the lock
        try:
            provider_info = f"({provider_name}) " if provider_name else ""

            # Gemini Balancer
            if self.balancer_enabled:
                initial_balancer_count = len(checkpoint.wait_send_balancer)
                checkpoint.wait_send_balancer.update(keys)
                new_balancer_count = len(checkpoint.wait_send_balancer)
                added_balancer_count = new_balancer_count - initial_balancer_count
                logger.info(f"📥 Added {added_balancer_count} {provider_info}key(s) to gemini balancer queue (total: {new_balancer_count})")
            else:
                logger.info(f"🚫 Gemini Balancer disabled, skipping {len(keys)} {provider_info}key(s) for gemini balancer queue")

            # GPT Load Balancer - 现在支持按供应商分组
            if self.gpt_load_enabled:
                # 使用提供的group_name或默认配置
                target_group_name = group_name if group_name else (self.gpt_load_group_names[0] if self.gpt_load_group_names else "")
                
                if target_group_name:
                    # 初始化分组队列
                    if not hasattr(checkpoint, 'wait_send_gpt_load_by_group'):
                        checkpoint.wait_send_gpt_load_by_group = {}
                    
                    # 获取或创建该分组的队列
                    group_queue = checkpoint.wait_send_gpt_load_by_group.get(target_group_name, set())
                    initial_group_count = len(group_queue)
                    
                    # 添加密钥到分组队列
                    group_queue.update(keys)
                    checkpoint.wait_send_gpt_load_by_group[target_group_name] = group_queue
                    
                    new_group_count = len(group_queue)
                    added_group_count = new_group_count - initial_group_count
                    logger.info(f"📥 Added {added_group_count} {provider_info}key(s) to GPT load group '{target_group_name}' queue (total: {new_group_count})")
                else:
                    logger.warning(f"⚠️ No group name specified for {provider_info}keys, skipping GPT Load Balancer")
            else:
                logger.info(f"🚫 GPT Load Balancer disabled, skipping {len(keys)} {provider_info}key(s)")

            file_manager.save_checkpoint(checkpoint)
        finally:
            self.saving_checkpoint = False  # Release the lock

    def _send_balancer_worker(self, keys: List[str]) -> str:
        """
        实际执行发送到balancer的工作函数（在后台线程中执行）
        
        Args:
            keys: API keys列表
            
        Returns:
            str: "ok" if success, otherwise an error code string.
        """
        try:
            logger.info(f"🔄 Sending {len(keys)} key(s) to balancer...")

            # 1. 获取当前配置
            config_url = f"{self.balancer_url}/api/config"
            headers = {
                'Cookie': f'auth_token={self.balancer_auth}',
                'User-Agent': 'HajimiKing/1.0'
            }

            logger.info(f"📥 Fetching current config from: {config_url}")

            # 获取当前配置
            response = requests.get(config_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"Failed to get config: HTTP {response.status_code} - {response.text}")
                return "get_config_failed_not_200"

            # 解析配置
            config_data = response.json()

            # 2. 获取当前的API_KEYS数组
            current_api_keys = config_data.get('API_KEYS', [])

            # 3. 合并新keys（去重）
            existing_keys_set = set(current_api_keys)
            new_add_keys_set = set()
            for key in keys:
                if key not in existing_keys_set:
                    existing_keys_set.add(key)
                    new_add_keys_set.add(key)

            if len(new_add_keys_set) == 0:
                logger.info(f"ℹ️ All {len(keys)} key(s) already exist in balancer")
                # 不需要记录发送结果，因为没有实际发送新密钥
                return "ok"

            # 4. 更新配置中的API_KEYS
            config_data['API_KEYS'] = list(existing_keys_set)

            logger.info(f"📝 Updating gemini balancer config with {len(new_add_keys_set)} new key(s)...")

            # 5. 发送更新后的配置到服务器
            update_headers = headers.copy()
            update_headers['Content-Type'] = 'application/json'

            update_response = requests.put(
                config_url,
                headers=update_headers,
                json=config_data,
                timeout=60
            )

            if update_response.status_code != 200:
                logger.error(f"Failed to update config: HTTP {update_response.status_code} - {update_response.text}")
                return "update_config_failed_not_200"

            # 6. 验证是否添加成功
            updated_config = update_response.json()
            updated_api_keys = updated_config.get('API_KEYS', [])
            updated_keys_set = set(updated_api_keys)

            failed_to_add = [key for key in new_add_keys_set if key not in updated_keys_set]

            if failed_to_add:
                logger.error(f"❌ Failed to add {len(failed_to_add)} key(s): {[key[:10] + '...' for key in failed_to_add]}")
                # 保存发送结果日志 - 部分成功的情况
                send_result = {}
                keys_to_log = []
                for key in new_add_keys_set:  # 只记录尝试新增的密钥
                    if key in failed_to_add:
                        send_result[key] = "update_failed"
                        keys_to_log.append(key)
                    else:
                        send_result[key] = "ok"
                        keys_to_log.append(key)
                if keys_to_log:  # 只有当有需要记录的密钥时才记录
                    file_manager.save_keys_send_result(keys_to_log, send_result)
                return "update_failed"


            logger.info(f"✅ All {len(new_add_keys_set)} new key(s) successfully added to balancer.")
            
            # 保存发送结果日志 - 只记录实际新增的密钥
            send_result = {key: "ok" for key in new_add_keys_set}
            if send_result:  # 只有当有新增密钥时才记录
                file_manager.save_keys_send_result(list(new_add_keys_set), send_result)
            
            return "ok"

        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout when connecting to balancer")
            # 保存发送结果日志 - 所有密钥都失败
            send_result = {key: "timeout" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "timeout"
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection failed to balancer")
            # 保存发送结果日志 - 所有密钥都失败
            send_result = {key: "connection_error" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "connection_error"
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON response from balancer: {str(e)}")
            # 保存发送结果日志 - 所有密钥都失败
            send_result = {key: "json_decode_error" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "json_decode_error"
        except Exception as e:
            logger.error(f"❌ Failed to send keys to balancer: {str(e)}")
            traceback.print_exc()
            # 保存发送结果日志 - 所有密钥都失败
            send_result = {key: "exception" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "exception"

    def _get_gpt_load_group_id(self, group_name: str) -> Optional[int]:
        """
        获取GPT Load Balancer group ID，带缓存功能
        
        Args:
            group_name: 组名
            
        Returns:
            Optional[int]: 组ID，如果未找到则返回None
        """
        current_time = time.time()
        
        # 检查缓存是否有效
        if (group_name in self.group_id_cache and
            group_name in self.group_id_cache_time and
            current_time - self.group_id_cache_time[group_name] < self.group_id_cache_ttl):
            logger.info(f"📋 Using cached group ID for '{group_name}': {self.group_id_cache[group_name]}")
            return self.group_id_cache[group_name]
        
        # 缓存过期或不存在，重新获取
        try:
            groups_url = f"{self.gpt_load_url}/api/groups"
            headers = {
                'Authorization': f'Bearer {self.gpt_load_auth}',
                'User-Agent': 'HajimiKing/1.0'
            }

            logger.info(f"📥 Fetching groups from: {groups_url}")

            response = requests.get(groups_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"Failed to get groups: HTTP {response.status_code} - {response.text}")
                return None

            groups_data = response.json()
            
            if groups_data.get('code') != 0:
                logger.error(f"Groups API returned error: {groups_data.get('message', 'Unknown error')}")
                return None

            # 查找指定group的ID
            groups_list = groups_data.get('data', [])
            for group in groups_list:
                if group.get('name') == group_name:
                    group_id = group.get('id')
                    # 更新缓存
                    self.group_id_cache[group_name] = group_id
                    self.group_id_cache_time[group_name] = current_time
                    logger.info(f"✅ Found and cached group '{group_name}' with ID: {group_id}")
                    return group_id

            logger.error(f"Group '{group_name}' not found in groups list")
            return None

        except Exception as e:
            logger.error(f"❌ Failed to get group ID for '{group_name}': {str(e)}")
            return None

    def _send_gpt_load_worker(self, keys: List[str], group_name: str = "") -> str:
        """
        实际执行发送到GPT load balancer的工作函数（在后台线程中执行）
        
        Args:
            keys: API keys列表
            group_name: GPT Load Group名称（如果提供，将只发送到指定group）
            
        Returns:
            str: "ok" if success, otherwise an error code string.
        """
        try:
            # 如果提供了group_name，只发送到指定group；否则发送到所有group
            target_group_names = [group_name] if group_name else self.gpt_load_group_names
            
            logger.info(f"🔄 Sending {len(keys)} key(s) to GPT load balancer for {len(target_group_names)} group(s)...")

            # 遍历目标group names，为每个group发送keys
            all_success = True
            failed_groups = []
            
            for target_group_name in target_group_names:
                logger.info(f"📝 Processing group: {target_group_name}")
                
                # 1. 获取group ID (使用缓存)
                group_id = self._get_gpt_load_group_id(target_group_name)
                
                if group_id is None:
                    logger.error(f"Failed to get group ID for '{target_group_name}'")
                    failed_groups.append(target_group_name)
                    all_success = False
                    continue

                # 2. 发送keys到指定group
                add_keys_url = f"{self.gpt_load_url}/api/keys/add-async"
                keys_text = ",".join(keys)
                
                add_headers = {
                    'Authorization': f'Bearer {self.gpt_load_auth}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'HajimiKing/1.0'
                }

                payload = {
                    "group_id": group_id,
                    "keys_text": keys_text
                }

                logger.info(f"📝 Adding {len(keys)} key(s) to group '{target_group_name}' (ID: {group_id})...")

                try:
                    # 发送添加keys请求
                    add_response = requests.post(
                        add_keys_url,
                        headers=add_headers,
                        json=payload,
                        timeout=60
                    )

                    if add_response.status_code != 200:
                        logger.error(f"Failed to add keys to group '{target_group_name}': HTTP {add_response.status_code} - {add_response.text}")
                        failed_groups.append(target_group_name)
                        all_success = False
                        continue

                    # 解析添加keys响应
                    add_data = add_response.json()
                    
                    if add_data.get('code') != 0:
                        logger.error(f"Add keys API returned error for group '{target_group_name}': {add_data.get('message', 'Unknown error')}")
                        failed_groups.append(target_group_name)
                        all_success = False
                        continue

                    # 检查任务状态
                    task_data = add_data.get('data', {})
                    task_type = task_data.get('task_type')
                    is_running = task_data.get('is_running')
                    total = task_data.get('total', 0)
                    response_group_name = task_data.get('group_name')

                    logger.info(f"✅ Keys addition task started successfully for group '{target_group_name}':")
                    logger.info(f"   Task Type: {task_type}")
                    logger.info(f"   Is Running: {is_running}")
                    logger.info(f"   Total Keys: {total}")
                    logger.info(f"   Group Name: {response_group_name}")

                except Exception as e:
                    logger.error(f"❌ Exception when adding keys to group '{target_group_name}': {str(e)}")
                    failed_groups.append(target_group_name)
                    all_success = False
                    continue

            # 根据结果返回状态
            if all_success:
                logger.info(f"✅ Successfully sent keys to all {len(target_group_names)} group(s)")
                # 保存发送结果日志 - 所有密钥都成功
                send_result = {key: "ok" for key in keys}
                file_manager.save_keys_send_result(keys, send_result)
                return "ok"
            else:
                logger.error(f"❌ Failed to send keys to {len(failed_groups)} group(s): {', '.join(failed_groups)}")
                # 保存发送结果日志 - 部分或全部失败
                send_result = {key: f"partial_failure_{len(failed_groups)}_groups" for key in keys}
                file_manager.save_keys_send_result(keys, send_result)
                return "partial_failure"

        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout when connecting to GPT load balancer")
            send_result = {key: "timeout" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "timeout"
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection failed to GPT load balancer")
            send_result = {key: "connection_error" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "connection_error"
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON response from GPT load balancer: {str(e)}")
            send_result = {key: "json_decode_error" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "json_decode_error"
        except Exception as e:
            logger.error(f"❌ Failed to send keys to GPT load balancer: {str(e)}")
            send_result = {key: "exception" for key in keys}
            file_manager.save_keys_send_result(keys, send_result)
            return "exception"

    def _start_batch_sender(self) -> None:
        """启动批量发送定时器"""
        if self.shutdown_flag:
            return

        # 启动发送任务
        self.executor.submit(self._batch_send_worker)

        # 设置下一次发送定时器
        self.batch_timer = threading.Timer(self.batch_interval, self._start_batch_sender)
        self.batch_timer.daemon = True
        self.batch_timer.start()

    def _batch_send_worker(self) -> None:
        """批量发送worker - 数据库模式下禁用"""
        # 数据库模式下禁用此功能，同步由 Web 界面手动触发
        return

        # 以下代码仅在文件模式下使用
        while self.saving_checkpoint:
            logger.info(f"📥 Checkpoint is currently being saving, waiting before batch sending...")
            time.sleep(1)

        self.saving_checkpoint = True
        try:
            logger.info(f"📥 Starting batch sending (disabled)")
            # 发送gemini balancer队列
            if checkpoint.wait_send_balancer and self.balancer_enabled:
                balancer_keys = list(checkpoint.wait_send_balancer)
                logger.info(f"🔄 Processing {len(balancer_keys)} key(s) from gemini balancer queue")

                result_code = self._send_balancer_worker(balancer_keys)
                if result_code == 'ok':
                    # 清空队列
                    checkpoint.wait_send_balancer.clear()
                    logger.info(f"✅ Gemini balancer queue processed successfully, cleared {len(balancer_keys)} key(s)")
                else:
                    logger.error(f"❌ Gemini balancer queue processing failed with code: {result_code}")

            # 发送gpt_load队列（旧队列，向后兼容）
            if checkpoint.wait_send_gpt_load and self.gpt_load_enabled:
                gpt_load_keys = list(checkpoint.wait_send_gpt_load)
                logger.info(f"🔄 Processing {len(gpt_load_keys)} key(s) from GPT load balancer queue")

                result_code = self._send_gpt_load_worker(gpt_load_keys)

                if result_code == 'ok':
                    # 清空队列
                    checkpoint.wait_send_gpt_load.clear()
                    logger.info(f"✅ GPT load balancer queue processed successfully, cleared {len(gpt_load_keys)} key(s)")
                else:
                    logger.error(f"❌ GPT load balancer queue processing failed with code: {result_code}")

            # 发送gpt_load分组队列（新队列）
            if hasattr(checkpoint, 'wait_send_gpt_load_by_group') and checkpoint.wait_send_gpt_load_by_group and self.gpt_load_enabled:
                total_group_keys = 0
                processed_groups = []
                
                # 复制分组队列以避免在迭代时修改
                groups_to_process = list(checkpoint.wait_send_gpt_load_by_group.keys())
                
                for group_name in groups_to_process:
                    group_queue = checkpoint.wait_send_gpt_load_by_group.get(group_name, set())
                    if group_queue:
                        gpt_load_keys = list(group_queue)
                        total_group_keys += len(gpt_load_keys)
                        logger.info(f"🔄 Processing {len(gpt_load_keys)} key(s) from GPT load group '{group_name}' queue")

                        result_code = self._send_gpt_load_worker(gpt_load_keys, group_name)

                        if result_code == 'ok':
                            # 清空该分组队列
                            checkpoint.wait_send_gpt_load_by_group[group_name].clear()
                            processed_groups.append(group_name)
                            logger.info(f"✅ GPT load group '{group_name}' queue processed successfully, cleared {len(gpt_load_keys)} key(s)")
                        else:
                            logger.error(f"❌ GPT load group '{group_name}' queue processing failed with code: {result_code}")
                
                if processed_groups:
                    logger.info(f"✅ GPT load group queues processed successfully for groups: {', '.join(processed_groups)}, total {total_group_keys} key(s)")

            # 保存checkpoint
            file_manager.save_checkpoint(checkpoint)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"❌ Batch send worker error: {e}\n{stacktrace}")
            logger.error(f"❌ Batch send worker error: {e}")
        finally:
            self.saving_checkpoint = False  # Release the lock

    def shutdown(self) -> None:
        """关闭线程池和定时器"""
        self.shutdown_flag = True

        if self.batch_timer:
            self.batch_timer.cancel()

        self.executor.shutdown(wait=True)
        logger.info("🔚 SyncUtils shutdown complete")


# 创建全局实例
sync_utils = SyncUtils()
