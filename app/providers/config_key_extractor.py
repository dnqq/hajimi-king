import re
from typing import Dict, List, Set
from .config_based_factory import ConfigBasedAIProviderFactory


class ConfigKeyExtractor:
    """基于配置的密钥提取工具类"""
    
    @staticmethod
    def extract_all_keys(content: str) -> Dict[str, List[str]]:
        """
        从内容中提取所有支持的供应商密钥
        
        Args:
            content: 要提取密钥的内容
            
        Returns:
            Dict[str, List[str]]: 按供应商分类的密钥字典
        """
        providers = ConfigBasedAIProviderFactory.get_all_providers()
        result = {}
        
        for provider_name, provider in providers.items():
            try:
                keys = provider.extract_keys_from_content(content)
                if keys:
                    result[provider_name] = keys
            except Exception as e:
                logger.error(f"Failed to extract keys for {provider_name}: {e}")
                continue
        
        return result
    
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
        from common.config import Config
        
        for provider_config in Config.AI_PROVIDERS_CONFIG:
            if provider_config.get('name') == provider_name:
                return provider_config.get('gpt_load_group_name', '')
        
        return ""


# 全局实例
config_key_extractor = ConfigKeyExtractor()