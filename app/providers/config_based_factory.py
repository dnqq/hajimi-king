import os
import re
from typing import Dict, List, Optional, Union, Any
from abc import ABC, abstractmethod

from common.Logger import logger
from common.config import config


class ConfigBasedAIProvider(ABC):
    """基于配置的AI供应商基类"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        self.config = provider_config
        self.name = provider_config.get('name', 'unknown')
        
    @abstractmethod
    def validate_key(self, api_key: str) -> Union[bool, str]:
        """验证API密钥"""
        pass
    
    @abstractmethod
    def extract_keys_from_content(self, content: str) -> List[str]:
        """从内容中提取密钥"""
        pass
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """获取随机代理配置"""
        from common.config import config
        return config.get_random_proxy()


class OpenAIStyleProvider(ConfigBasedAIProvider):
    """OpenAI风格供应商（支持OpenAI、OpenRouter等兼容API）"""
    
    def validate_key(self, api_key: str) -> Union[bool, str]:
        """验证OpenAI风格API密钥"""
        try:
            import openai
            from openai import OpenAI, AuthenticationError, RateLimitError, APIError
        except ImportError:
            return "error:openai_package_not_available"
        
        try:
            import time
            import random
            time.sleep(random.uniform(1, 5))
            
            # 获取代理配置
            proxy_config = self.get_random_proxy()
            
            # 创建客户端配置
            client_kwargs = {
                "api_key": api_key,
                "base_url": self.config.get('api_base_url', 'https://api.openai.com/v1')
            }
            
            # 设置代理
            if proxy_config:
                import httpx
                proxy_url = proxy_config.get('http') or proxy_config.get('https')
                if proxy_url:
                    client_kwargs["http_client"] = httpx.Client(proxies=proxy_url)
            
            client = OpenAI(**client_kwargs)
            
            # 发送简单验证请求
            response = client.chat.completions.create(
                model=self.config.get('check_model', 'gpt-3.5-turbo'),
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            
            return "ok"
            
        except AuthenticationError:
            return "not_authorized_key"
        except RateLimitError:
            return "rate_limited"
        except APIError as e:
            if "quota" in str(e).lower() or "limit" in str(e).lower():
                return "rate_limited:429"
            elif "disabled" in str(e).lower() or "deactivated" in str(e).lower():
                return "disabled"
            else:
                return f"error:{e.__class__.__name__}"
        except Exception as e:
            return f"error:{e.__class__.__name__}"
    
    def extract_keys_from_content(self, content: str) -> List[str]:
        """从内容中提取密钥"""
        key_patterns = self.config.get('key_patterns', [])
        keys = []
        
        for pattern in key_patterns:
            try:
                found_keys = re.findall(pattern, content)
                keys.extend(found_keys)
            except Exception as e:
                logger.warning(f"Failed to extract keys with pattern {pattern}: {e}")
        
        return list(set(keys))  # 去重


class GeminiProvider(ConfigBasedAIProvider):
    """Gemini供应商"""
    
    def validate_key(self, api_key: str) -> Union[bool, str]:
        """验证Gemini API密钥"""
        try:
            import time
            import random
            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            
            time.sleep(random.uniform(1, 5))
            
            # 获取代理配置
            proxy_config = self.get_random_proxy()
            
            client_options = {
                "api_endpoint": self.config.get('api_endpoint', 'generativelanguage.googleapis.com')
            }
            
            # 如果有代理配置，添加到client_options中
            if proxy_config:
                import os
                os.environ['grpc_proxy'] = proxy_config.get('http')
            
            genai.configure(
                api_key=api_key,
                client_options=client_options,
            )
            
            model = genai.GenerativeModel(self.config.get('check_model', 'gemini-2.5-flash'))
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
    
    def extract_keys_from_content(self, content: str) -> List[str]:
        """从内容中提取Gemini密钥"""
        key_patterns = self.config.get('key_patterns', [r'(AIzaSy[A-Za-z0-9\\-_]{33})'])
        keys = []
        
        for pattern in key_patterns:
            try:
                found_keys = re.findall(pattern, content)
                keys.extend(found_keys)
            except Exception as e:
                logger.warning(f"Failed to extract keys with pattern {pattern}: {e}")
        
        return list(set(keys))


class ConfigBasedAIProviderFactory:
    """基于配置的AI供应商工厂"""
    
    _provider_types = {
        'openai_style': OpenAIStyleProvider,
        'gemini': GeminiProvider
    }
    
    @classmethod
    def register_provider_type(cls, provider_type: str, provider_class):
        """注册供应商类型"""
        cls._provider_types[provider_type] = provider_class
    
    @classmethod
    def get_provider(cls, provider_config: Dict[str, Any]) -> ConfigBasedAIProvider:
        """根据配置获取供应商实例"""
        provider_type = provider_config.get('type', 'openai_style')
        
        if provider_type not in cls._provider_types:
            raise ValueError(f"Provider type {provider_type} not registered")
        
        provider_class = cls._provider_types[provider_type]
        return provider_class(provider_config)
    
    @classmethod
    def get_all_providers(cls) -> Dict[str, ConfigBasedAIProvider]:
        """获取所有配置的供应商实例"""
        from common.config import config
        providers = {}
        
        for provider_config in config.AI_PROVIDERS_CONFIG:
            try:
                provider = cls.get_provider(provider_config)
                providers[provider.name] = provider
            except Exception as e:
                logger.error(f"Failed to create provider {provider_config.get('name')}: {e}")
        
        return providers
    
    @classmethod
    def get_provider_by_name(cls, name: str) -> Optional[ConfigBasedAIProvider]:
        """根据名称获取供应商实例"""
        for provider_config in config.AI_PROVIDERS_CONFIG:
            if provider_config.get('name') == name:
                return cls.get_provider(provider_config)
        return None