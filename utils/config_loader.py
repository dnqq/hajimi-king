"""
配置加载器 - 优先从数据库读取配置，回退到 .env
"""
import os
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from common.Logger import logger
from web.database import SessionLocal
from web.models import SystemConfig


class ConfigLoader:
    """配置加载器"""

    def __init__(self):
        self._cache = {}

    def get_config(self, key: str, env_key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值（优先数据库，回退 .env）

        Args:
            key: 数据库配置键
            env_key: 环境变量键（如果为 None，则使用 key）
            default: 默认值

        Returns:
            配置值
        """
        # 1. 尝试从数据库读取
        try:
            db = SessionLocal()
            try:
                config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                if config:
                    logger.debug(f"✅ Loaded config from DB: {key}")
                    return config.value
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"⚠️ Failed to load config from DB ({key}): {e}")

        # 2. 回退到环境变量
        env_key = env_key or key.upper()
        env_value = os.getenv(env_key)

        if env_value is not None:
            logger.debug(f"📄 Loaded config from .env: {env_key}")
            return self._parse_env_value(env_value)

        # 3. 返回默认值
        logger.debug(f"🔧 Using default config: {key} = {default}")
        return default

    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值（尝试 JSON 解析）"""
        if not value:
            return value

        # 尝试解析为 JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def get_ai_providers(self) -> List[Dict[str, Any]]:
        """获取 AI 供应商配置（从 ai_providers 表读取）"""
        try:
            from web.models import AIProvider
            db = SessionLocal()
            try:
                providers = db.query(AIProvider).filter(AIProvider.enabled == True).order_by(AIProvider.sort_order).all()
                if providers:
                    return [provider.to_dict() for provider in providers]
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"⚠️ Failed to load providers from table: {e}")

        # 回退：从 system_config 读取（兼容旧数据）
        providers = self.get_config('ai_providers', 'AI_PROVIDERS_CONFIG', [])
        if providers:
            logger.info("📄 Loaded providers from system_config (fallback)")
            return providers

        # 最终回退：默认配置
        logger.warning("⚠️ No providers found, using default config")
        return [
            {
                "name": "gemini",
                "type": "gemini",
                "check_model": "gemini-2.0-flash-exp",
                "api_endpoint": "generativelanguage.googleapis.com",
                "key_patterns": ["AIzaSy[A-Za-z0-9\\\\-_]{33}"],
                "gpt_load_group_name": "",
                "skip_ai_analysis": True,
                "custom_keywords": []
            }
        ]

    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置"""
        return self.get_config('sync_config', None, {
            "gemini_balancer_enabled": os.getenv("GEMINI_BALANCER_SYNC_ENABLED", "false").lower() in ("true", "1", "yes"),
            "gemini_balancer_url": os.getenv("GEMINI_BALANCER_URL", ""),
            "gemini_balancer_auth": os.getenv("GEMINI_BALANCER_AUTH", ""),
            "gpt_load_enabled": os.getenv("GPT_LOAD_SYNC_ENABLED", "false").lower() in ("true", "1", "yes"),
            "gpt_load_url": os.getenv("GPT_LOAD_URL", ""),
            "gpt_load_auth": os.getenv("GPT_LOAD_AUTH", "")
        })

    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置"""
        return self.get_config('search_config', None, {
            "date_range_days": int(os.getenv("DATE_RANGE_DAYS", "730")),
            "file_path_blacklist": [
                token.strip().lower()
                for token in os.getenv("FILE_PATH_BLACKLIST", "readme,docs,doc/,.md,example,sample,tutorial").split(',')
                if token.strip()
            ]
        })

    def get_ai_analysis_config(self) -> Dict[str, Any]:
        """获取 AI 分析配置"""
        return self.get_config('ai_analysis_config', None, {
            "enabled": os.getenv("AI_ANALYSIS_ENABLED", "false").lower() in ("true", "1", "yes"),
            "url": os.getenv("AI_ANALYSIS_URL", ""),
            "model": os.getenv("AI_ANALYSIS_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("AI_ANALYSIS_API_KEY", "")
        })

    def get_github_config(self) -> Dict[str, Any]:
        """获取 GitHub 配置"""
        return self.get_config('github_config', None, {
            "tokens": [
                token.strip()
                for token in os.getenv("GITHUB_TOKENS", "").split(',')
                if token.strip()
            ],
            "proxy": [
                proxy.strip()
                for proxy in os.getenv("PROXY", "").split(',')
                if proxy.strip()
            ]
        })


# 全局实例
config_loader = ConfigLoader()
