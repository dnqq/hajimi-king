import json
import re
import requests
from typing import Dict, List, Optional, Tuple, Any
from common.Logger import logger
from common.config import Config
from app.providers.key_extractor import KeyExtractor


class AIAnalyzer:
    """AI分析服务，用于分析文件内容并提取API密钥和配置信息"""
    
    def __init__(self):
        self.enabled = Config.AI_ANALYSIS_ENABLED
        self.api_url = Config.AI_ANALYSIS_URL
        self.model = Config.AI_ANALYSIS_MODEL
        self.api_key = Config.AI_ANALYSIS_API_KEY
        # 检查是否启用了AI分析
        if self.enabled and (not self.api_url or not self.api_key):
            logger.warning("⚠️ AI分析已启用但缺少URL或API密钥配置")
            self.enabled = False
        # 如果配置要求跳过AI分析，则也禁用AI分析
        if KeyExtractor.should_skip_ai_analysis_by_config(self.api_key):
            logger.info("⏩ 根据配置跳过AI分析")
            self.enabled = False
     
    def extract_api_info(self, content: str, file_path: str, key: str) -> Optional[Dict]:
        """
        使用AI分析文件内容，提取特定API密钥的URL和模型信息
        如果配置了skip_ai_analysis且密钥符合已知格式，则跳过AI分析
        """
        # 如果已配置跳过AI分析且密钥符合格式，则直接返回空，不进行AI分析
        if KeyExtractor.should_skip_ai_analysis_by_config(key):
            logger.info(f"⏩ 根据配置跳过AI分析: {key[:10]}...")
            return None

        if not self.enabled or not content or not key:
            return None
            
        try:
            # 构建AI请求
            prompt = self._build_extraction_prompt(content, file_path, key)
            response = self._call_ai_api(prompt)
            
            if response:
                return self._parse_extraction_response(response)
                
        except Exception as e:
            logger.error(f"❌ AI分析失败: {e}")
            
        return None
    
    def _build_extraction_prompt(self, content: str, file_path: str, key: str) -> str:
        """构建AI提取提示词，专注于提取特定密钥的API信息"""
        # 截取文件内容的前1000字符以避免token限制
        truncated_content = content[:1000] + "..." if len(content) > 1000 else content
        
        return f"""请分析以下代码文件内容，提取特定API密钥的配置信息。

文件路径: {file_path}
需要分析的API密钥: {key[:10]}...{key[-4:]}

请专注于分析这个特定密钥的配置，找出：
1. 这个API密钥对应的基础URL（API endpoint）
2. 这个API使用的模型名称

文件内容:
```
{truncated_content}
```

请按照以下JSON格式返回分析结果：
{{
  "base_url": "API基础URL（例如：https://api.openai.com/v1）",
  "model": "使用的模型名称（例如：gpt-3.5-turbo）",
  "service_type": "服务类型"
}}

如果无法确定URL或模型信息，返回空对象。
请确保只返回有效的JSON格式，不要包含其他文本。"""
    
    def _parse_extraction_response(self, response: str) -> Optional[Dict]:
        """解析AI返回的API信息响应"""
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                # 确保包含必要的字段
                if result.get('base_url') and result.get('model'):
                    return result
            return None
        except Exception as e:
            logger.error(f"❌ AI响应解析失败: {e}, 响应内容: {response[:200]}...")
            return None
    
    def _build_analysis_prompt(self, content: str, file_path: str) -> str:
        """构建AI分析提示词"""
        # 截取文件内容的前1000字符以避免token限制
        truncated_content = content[:1000] + "..." if len(content) > 1000 else content
        
        return f"""请分析以下代码文件内容，提取所有可用的API密钥和相关的服务配置信息。

文件路径: {file_path}

文件内容:
```
{truncated_content}
```

请按照以下JSON格式返回分析结果：
{{
  "api_keys": [
    {{
      "key": "实际的API密钥字符串",
      "service_type": "服务类型（如openai、anthropic、cohere、huggingface等）",
      "base_url": "API基础URL（如果可识别）",
      "model": "使用的模型名称（如果可识别）"
    }}
  ],
  "configurations": [
    {{
      "key": "配置键名",
      "value": "配置值",
      "description": "配置描述"
    }}
  ]
}}

如果找不到任何API密钥或配置信息，返回空数组。
请确保只返回有效的JSON格式，不要包含其他文本。"""
    
    def _call_ai_api(self, prompt: str) -> Optional[str]:
        """调用AI API"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的代码分析助手，擅长从代码中提取API密钥和配置信息。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            
            response = requests.post(
                f"{self.api_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"❌ AI API调用失败: {e}")
            return None
    
    def _parse_ai_response(self, response: str) -> Optional[Dict]:
        """解析AI返回的JSON响应"""
        try:
            # 提取JSON部分（AI可能会在响应中添加其他文本）
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response)
        except Exception as e:
            logger.error(f"❌ AI响应解析失败: {e}, 响应内容: {response[:200]}...")
            return None
    
    def validate_key_with_openai_format(self, api_key: str, base_url: str, model: str = "gpt-3.5-turbo") -> Tuple[bool, str]:
        """
        使用OpenAI格式验证API密钥
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 用于验证的模型名称
            
        Returns:
            Tuple[bool, str]: (是否有效, 验证结果信息)
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            }
            
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                return True, "valid"
            elif response.status_code == 401:
                return False, "invalid_key"
            elif response.status_code == 429:
                return False, "rate_limited"
            else:
                return False, f"http_error_{response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, "connection_error"
        except requests.exceptions.Timeout:
            return False, "timeout"
        except Exception as e:
            return False, f"error: {str(e)}"


# 创建全局实例
ai_analyzer = AIAnalyzer()