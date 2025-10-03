import json
import time
import traceback
from typing import List, Dict, Optional

import requests

from common.Logger import logger
from common.config import config


class SyncUtils:
    """同步工具类，负责发送keys到外部应用（数据库模式）"""

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

    def _send_balancer_worker(self, keys: List[str]) -> str:
        """
        发送到 Gemini Balancer

        Args:
            keys: API keys列表

        Returns:
            str: "success" if success, otherwise an error code string.
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
                return f"get_config_failed_{response.status_code}"

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
                return "success"

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
                return f"update_config_failed_{update_response.status_code}"

            # 6. 验证是否添加成功
            updated_config = update_response.json()
            updated_api_keys = updated_config.get('API_KEYS', [])
            updated_keys_set = set(updated_api_keys)

            failed_to_add = [key for key in new_add_keys_set if key not in updated_keys_set]

            if failed_to_add:
                logger.error(f"❌ Failed to add {len(failed_to_add)} key(s): {[key[:10] + '...' for key in failed_to_add]}")
                return "update_failed"

            logger.info(f"✅ All {len(new_add_keys_set)} new key(s) successfully added to balancer.")
            return "success"

        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout when connecting to balancer")
            return "timeout"
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection failed to balancer")
            return "connection_error"
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON response from balancer: {str(e)}")
            return "json_decode_error"
        except Exception as e:
            logger.error(f"❌ Failed to send keys to balancer: {str(e)}")
            traceback.print_exc()
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
        发送到 GPT Load Balancer

        Args:
            keys: API keys列表
            group_name: GPT Load Group名称（如果提供，将只发送到指定group）

        Returns:
            str: "success" if success, otherwise an error code string.
        """
        try:
            # 如果提供了group_name（非空字符串），只发送到指定group；否则发送到所有group
            target_group_names = [group_name] if (group_name and group_name.strip()) else self.gpt_load_group_names

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
                return "success"
            else:
                logger.error(f"❌ Failed to send keys to {len(failed_groups)} group(s): {', '.join(failed_groups)}")
                return "partial_failure"

        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout when connecting to GPT load balancer")
            return "timeout"
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection failed to GPT load balancer")
            return "connection_error"
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON response from GPT load balancer: {str(e)}")
            return "json_decode_error"
        except Exception as e:
            logger.error(f"❌ Failed to send keys to GPT load balancer: {str(e)}")
            return "exception"


# 创建全局实例
sync_utils = SyncUtils()
