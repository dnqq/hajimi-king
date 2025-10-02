import re
from typing import Dict, List, Set
from .config_based_factory import ConfigBasedAIProviderFactory


class KeyExtractor:
    """密钥提取工具类"""
    
    @staticmethod
    def should_skip_ai_analysis_by_config(key: str) -> bool:
        """
        根据配置中的正则表达式检查是否应该跳过AI分析
        只有当供应商配置了 skip_ai_analysis: true 时，才检查密钥格式
        否则一律不跳过AI分析（即使格式匹配）
        
        Args:
            key: API密钥
            
        Returns:
            bool: 如果供应商配置了skip_ai_analysis且密钥格式匹配，返回True
        """
        from common.config import config
        
        # 遍历所有供应商配置中的密钥模式
        for provider_config in config.AI_PROVIDERS_CONFIG:
            # 检查是否启用了跳过AI分析
            skip_ai_analysis = provider_config.get('skip_ai_analysis', False)
            if not skip_ai_analysis:
                continue
                
            key_patterns = provider_config.get('key_patterns', [])
            
            # 检查密钥是否匹配任何一个模式
            for pattern in key_patterns:
                try:
                    import re
                    # 匹配整个字符串，确保完全符合模式
                    if re.fullmatch(pattern.replace('\\\\', '\\'), key):
                        return True
                except Exception as e:
                    # 忽略正则表达式错误
                    continue
        
        return False
    
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
                # 忽略供应商实例化错误
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
            return []
        
        return []
    
    @staticmethod
    def identify_provider_from_key(api_key: str) -> str:
        """
        根据密钥格式识别供应商
        
        Args:
            api_key: API密钥
            
        Returns:
            str: 供应商名称或"unknown"
        """
        # Gemini密钥格式: AIzaSy开头，33个字符
        if re.match(r'^AIzaSy[A-Za-z0-9\\-_]{33}$', api_key):
            return "gemini"
        
        # OpenAI密钥格式: sk-开头，20-100个字符
        if re.match(r'^sk-[A-Za-z0-9\\-_]{20,100}$', api_key):
            return "openai"
        
        # OpenRouter密钥通常是较长的随机字符串
        if re.match(r'^[A-Za-z0-9\\-_]{40,100}$', api_key):
            return "openrouter"
        
        return "unknown"
    
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
        all_keys = KeyExtractor.extract_all_keys(content)
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
                # 忽略供应商处理错误
                continue
        
        return result