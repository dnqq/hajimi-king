import re
from typing import Dict, List, Set
from .config_based_factory import ConfigBasedAIProviderFactory


class ConfigKeyExtractor:
    """基于配置的密钥提取工具类"""
    
    @staticmethod
    def extract_all_keys(content: str) -> Dict[str, List[str]]:
        """
        从内容中提取所有支持的供应商密钥

        使用最具体匹配策略：
        1. 先提取所有 provider 的 keys
        2. 对于同一个 key，选择匹配前缀最长的 provider
           例如: "sk-or-v1-" (9字符) > "sk-" (3字符)

        Args:
            content: 要提取密钥的内容

        Returns:
            Dict[str, List[str]]: 按供应商分类的密钥字典
        """
        from common.Logger import logger

        providers = ConfigBasedAIProviderFactory.get_all_providers()

        # 第一步：提取所有 keys 及其匹配的 providers
        key_to_providers = {}  # {key: [(provider_name, prefix_specificity), ...]}

        for provider_name, provider in providers.items():
            try:
                keys = provider.extract_keys_from_content(content)
                if keys:
                    # 计算该 provider 的前缀具体程度
                    key_patterns = provider.config.get('key_patterns', [])

                    # 从 pattern 中提取固定前缀长度（非正则部分）
                    max_prefix_len = 0
                    for pattern in key_patterns:
                        prefix_len = ConfigKeyExtractor._get_fixed_prefix_length(pattern)
                        max_prefix_len = max(max_prefix_len, prefix_len)

                    for key in keys:
                        if key not in key_to_providers:
                            key_to_providers[key] = []
                        key_to_providers[key].append((provider_name, max_prefix_len))
            except Exception as e:
                logger.error(f"Failed to extract keys for {provider_name}: {e}")
                continue

        # 第二步：对每个 key，选择前缀最具体的 provider
        result = {}
        for key, providers_list in key_to_providers.items():
            # 按前缀长度降序排序，选择最具体的
            providers_list.sort(key=lambda x: x[1], reverse=True)
            best_provider = providers_list[0][0]

            if best_provider not in result:
                result[best_provider] = []
            result[best_provider].append(key)

            # 如果有多个 provider 匹配同一个 key，记录警告
            if len(providers_list) > 1:
                other_providers = [p[0] for p in providers_list[1:]]
                logger.debug(f"Key {key[:20]}... matched by multiple providers: {best_provider} (chosen, prefix={providers_list[0][1]}), {', '.join(other_providers)} (skipped)")

        return result

    @staticmethod
    def _get_fixed_prefix_length(pattern: str) -> int:
        """
        计算正则表达式的固定前缀长度

        例如:
        - "AIzaSy[A-Za-z0-9]{33}" → 6 ("AIzaSy")
        - "sk-or-v1-[A-Za-z0-9]{32}" → 9 ("sk-or-v1-")
        - "sk-[A-Za-z0-9]{20,}" → 3 ("sk-")
        - "csk-[A-Za-z0-9]+" → 4 ("csk-")

        Args:
            pattern: 正则表达式字符串

        Returns:
            int: 固定前缀的字符数
        """
        import re

        # 移除开头的 (?: 或 (
        clean_pattern = pattern.lstrip('(').lstrip('?:')

        prefix_len = 0
        i = 0
        while i < len(clean_pattern):
            char = clean_pattern[i]

            # 遇到正则元字符，停止计数
            if char in '[{*()+?.|\\':
                break

            # 普通字符，计入前缀
            prefix_len += 1
            i += 1

        return prefix_len
    
    @staticmethod
    def extract_keys_by_provider(content: str, provider_name: str) -> List[str]:
        """
        使用特定供应商的提取方法提取密钥
        
        Args:
            content: 要提取密钥的内容
            provider_name: 供应商名称
            
        Returns:
            List[str]: 提取到的密钥列表
        """
        try:
            provider = ConfigBasedAIProviderFactory.get_provider_by_name(provider_name)
            if provider:
                return provider.extract_keys_from_content(content)
        except Exception as e:
            logger.error(f"Error extracting keys for {provider_name}: {e}")
        
        return []
    
    @staticmethod
    def validate_and_classify_keys(content: str) -> Dict[str, Dict[str, List[str]]]:
        """
        提取、验证并分类所有密钥
        
        Args:
            content: 要处理的内容
            
        Returns:
            Dict[str, Dict[str, List[str]]]: 分类结果，格式为:
            {
                "valid": {"gemini": [...], "openai": [...]},
                "invalid": {"gemini": [...], "openai": [...]},
                "rate_limited": {"gemini": [...], "openai": [...]}
            }
        """
        all_keys = ConfigKeyExtractor.extract_all_keys(content)
        result = {
            "valid": {},
            "invalid": {},
            "rate_limited": {}
        }
        
        for provider_name, keys in all_keys.items():
            try:
                provider = ConfigBasedAIProviderFactory.get_provider_by_name(provider_name)
                if not provider:
                    continue
                
                valid_keys = []
                invalid_keys = []
                rate_limited_keys = []
                
                for key in keys:
                    validation_result = provider.validate_key(key)
                    if validation_result == "ok":
                        valid_keys.append(key)
                    elif "rate_limited" in validation_result:
                        rate_limited_keys.append(key)
                    else:
                        invalid_keys.append(key)
                
                if valid_keys:
                    result["valid"][provider_name] = valid_keys
                if invalid_keys:
                    result["invalid"][provider_name] = invalid_keys
                if rate_limited_keys:
                    result["rate_limited"][provider_name] = rate_limited_keys
                    
            except Exception as e:
                logger.error(f"Error processing {provider_name} keys: {e}")
                continue
        
        return result
    
    @staticmethod
    def get_gpt_load_group_name(provider_name: str) -> str:
        """
        获取供应商的GPT Load Group名称
        
        Args:
            provider_name: 供应商名称
            
        Returns:
            str: GPT Load Group名称
        """
        from common.config import config
        
        for provider_config in config.AI_PROVIDERS_CONFIG:
            if provider_config.get('name') == provider_name:
                return provider_config.get('gpt_load_group_name', '')
        
        return ""


# 全局实例
config_key_extractor = ConfigKeyExtractor()