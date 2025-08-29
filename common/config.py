import os
import random
from typing import Dict, Optional

from dotenv import load_dotenv

from common.Logger import logger

# 只在环境变量不存在时才从.env加载值
load_dotenv(override=False)


class Config:
    GITHUB_TOKENS_STR = os.getenv("GITHUB_TOKENS", "")

    # 获取GitHub tokens列表
    GITHUB_TOKENS = [token.strip() for token in GITHUB_TOKENS_STR.split(',') if token.strip()]
    DATA_PATH = os.getenv('DATA_PATH', '/app/data')
    PROXY_LIST_STR = os.getenv("PROXY", "")
    
    # 解析代理列表，支持格式：http://user:pass@host:port,http://host:port,socks5://user:pass@host:port
    PROXY_LIST = []
    if PROXY_LIST_STR:
        for proxy_str in PROXY_LIST_STR.split(','):
            proxy_str = proxy_str.strip()
            if proxy_str:
                PROXY_LIST.append(proxy_str)
    
    # Gemini Balancer配置
    GEMINI_BALANCER_SYNC_ENABLED = os.getenv("GEMINI_BALANCER_SYNC_ENABLED", "false")
    GEMINI_BALANCER_URL = os.getenv("GEMINI_BALANCER_URL", "")
    GEMINI_BALANCER_AUTH = os.getenv("GEMINI_BALANCER_AUTH", "")

    # GPT Load Balancer Configuration
    GPT_LOAD_SYNC_ENABLED = os.getenv("GPT_LOAD_SYNC_ENABLED", "false")
    GPT_LOAD_URL = os.getenv('GPT_LOAD_URL', '')
    GPT_LOAD_AUTH = os.getenv('GPT_LOAD_AUTH', '')
    GPT_LOAD_GROUP_NAME = os.getenv('GPT_LOAD_GROUP_NAME', '')
    
    # 多供应商配置 (JSON格式)
    AI_PROVIDERS_CONFIG_JSON = os.getenv("AI_PROVIDERS_CONFIG", "[]")
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gemini")
    
    # 解析供应商配置
    try:
        import json
        AI_PROVIDERS_CONFIG = json.loads(AI_PROVIDERS_CONFIG_JSON)
        if not isinstance(AI_PROVIDERS_CONFIG, list):
            AI_PROVIDERS_CONFIG = []
    except (json.JSONDecodeError, TypeError):
        AI_PROVIDERS_CONFIG = []
    
    # 如果没有配置供应商，使用默认配置
    if not AI_PROVIDERS_CONFIG:
        AI_PROVIDERS_CONFIG = [
            {
                "name": "gemini",
                "type": "gemini",
                "check_model": "gemini-2.5-flash",
                "api_endpoint": "generativelanguage.googleapis.com",
                "key_patterns": ["AIzaSy[A-Za-z0-9\\\\-_]{33}"],
                "gpt_load_group_name": os.getenv("GEMINI_GPT_LOAD_GROUP_NAME", ""),
                "skip_ai_analysis": False
            },
            {
                "name": "openai",
                "type": "openai_style", 
                "check_model": "gpt-3.5-turbo",
                "api_base_url": "https://api.openai.com/v1",
                "key_patterns": ["sk-[A-Za-z0-9\\\\-_]{20,100}"],
                "gpt_load_group_name": os.getenv("OPENAI_GPT_LOAD_GROUP_NAME", ""),
                "skip_ai_analysis": False
            },
            {
                "name": "openrouter",
                "type": "openai_style",
                "check_model": "openai/gpt-3.5-turbo",
                "api_base_url": "https://openrouter.ai/api/v1",
                "key_patterns": ["[A-Za-z0-9\\\\-_]{40,100}"],
                "gpt_load_group_name": os.getenv("OPENROUTER_GPT_LOAD_GROUP_NAME", ""),
                "skip_ai_analysis": False
            }
        ]
    
    # 获取启用的供应商名称列表
    AI_PROVIDERS = [provider.get('name') for provider in AI_PROVIDERS_CONFIG]

    # 文件前缀配置
    VALID_KEY_PREFIX = os.getenv("VALID_KEY_PREFIX", "keys/keys_valid_")
    RATE_LIMITED_KEY_PREFIX = os.getenv("RATE_LIMITED_KEY_PREFIX", "keys/key_429_")
    KEYS_SEND_PREFIX = os.getenv("KEYS_SEND_PREFIX", "keys/keys_send_")

    VALID_KEY_DETAIL_PREFIX = os.getenv("VALID_KEY_DETAIL_PREFIX", "logs/keys_valid_detail_")
    RATE_LIMITED_KEY_DETAIL_PREFIX = os.getenv("RATE_LIMITED_KEY_DETAIL_PREFIX", "logs/key_429_detail_")
    KEYS_SEND_DETAIL_PREFIX = os.getenv("KEYS_SEND_DETAIL_PREFIX", "logs/keys_send_detail_")
    
    # 日期范围过滤器配置 (单位：天)
    DATE_RANGE_DAYS = int(os.getenv("DATE_RANGE_DAYS", "730"))  # 默认730天 (约2年)

    # 查询文件路径配置
    QUERIES_FILE = os.getenv("QUERIES_FILE", "queries.txt")

    # 已扫描SHA文件配置
    SCANNED_SHAS_FILE = os.getenv("SCANNED_SHAS_FILE", "scanned_shas.txt")

    # Gemini模型配置
    HAJIMI_CHECK_MODEL = os.getenv("HAJIMI_CHECK_MODEL", "gemini-2.5-flash")

    # 文件路径黑名单配置
    FILE_PATH_BLACKLIST_STR = os.getenv("FILE_PATH_BLACKLIST", "readme,docs,doc/,.md,sample,tutorial")
    FILE_PATH_BLACKLIST = [token.strip().lower() for token in FILE_PATH_BLACKLIST_STR.split(',') if token.strip()]

    # AI分析配置
    AI_ANALYSIS_ENABLED = os.getenv("AI_ANALYSIS_ENABLED", "false").lower() in ("true", "1", "yes", "on")
    AI_ANALYSIS_URL = os.getenv("AI_ANALYSIS_URL", "")
    AI_ANALYSIS_MODEL = os.getenv("AI_ANALYSIS_MODEL", "gpt-4o-mini")
    AI_ANALYSIS_API_KEY = os.getenv("AI_ANALYSIS_API_KEY", "")

    @classmethod
    def parse_bool(cls, value: str) -> bool:
        """
        解析布尔值配置，支持多种格式
        
        Args:
            value: 配置值字符串
            
        Returns:
            bool: 解析后的布尔值
        """
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            value = value.strip().lower()
            return value in ('true', '1', 'yes', 'on', 'enabled')
        
        if isinstance(value, int):
            return bool(value)
        
        return False

    @classmethod
    def get_random_proxy(cls) -> Optional[Dict[str, str]]:
        """
        随机获取一个代理配置
        
        Returns:
            Optional[Dict[str, str]]: requests格式的proxies字典，如果未配置则返回None
        """
        if not cls.PROXY_LIST:
            return None
        
        # 随机选择一个代理
        proxy_url = random.choice(cls.PROXY_LIST).strip()
        
        # 返回requests格式的proxies字典
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    @classmethod
    def check(cls) -> bool:
        """
        检查必要的配置是否完整
        
        Returns:
            bool: 配置是否完整
        """
        logger.info("🔍 Checking required configurations...")
        
        errors = []
        
        # 检查GitHub tokens
        if not cls.GITHUB_TOKENS:
            errors.append("GitHub tokens not found. Please set GITHUB_TOKENS environment variable.")
            logger.error("❌ GitHub tokens: Missing")
        else:
            logger.info(f"✅ GitHub tokens: {len(cls.GITHUB_TOKENS)} configured")
        
        # 检查Gemini Balancer配置
        if cls.GEMINI_BALANCER_SYNC_ENABLED:
            logger.info(f"✅ Gemini Balancer enabled, URL: {cls.GEMINI_BALANCER_URL}")
            if not cls.GEMINI_BALANCER_AUTH or not cls.GEMINI_BALANCER_URL:
                logger.warning("⚠️ Gemini Balancer Auth or URL Missing (Balancer功能将被禁用)")
            else:
                logger.info(f"✅ Gemini Balancer Auth: ****")
        else:
            logger.info("ℹ️ Gemini Balancer URL: Not configured (Balancer功能将被禁用)")

        # 检查GPT Load Balancer配置
        if cls.parse_bool(cls.GPT_LOAD_SYNC_ENABLED):
            logger.info(f"✅ GPT Load Balancer enabled, URL: {cls.GPT_LOAD_URL}")
            if not cls.GPT_LOAD_AUTH or not cls.GPT_LOAD_URL or not cls.GPT_LOAD_GROUP_NAME:
                logger.warning("⚠️ GPT Load Balancer Auth, URL or Group Name Missing (Load Balancer功能将被禁用)")
            else:
                logger.info(f"✅ GPT Load Balancer Auth: ****")
                logger.info(f"✅ GPT Load Balancer Group Name: {cls.GPT_LOAD_GROUP_NAME}")
        else:
            logger.info("ℹ️ GPT Load Balancer: Not configured (Load Balancer功能将被禁用)")

        # 检查AI供应商配置
        logger.info(f"🤖 Configured AI providers: {len(cls.AI_PROVIDERS_CONFIG)}")
        for provider in cls.AI_PROVIDERS_CONFIG:
            provider_name = provider.get('name', 'unknown')
            provider_type = provider.get('type', 'unknown')
            group_name = provider.get('gpt_load_group_name', 'not configured')
            skip_ai = provider.get('skip_ai_analysis', False)
            logger.info(f"   - {provider_name} ({provider_type}): GPT Load Group = {group_name}, Skip AI = {skip_ai}")
        
        logger.info(f"🔧 Default provider: {cls.DEFAULT_PROVIDER}")
        logger.info(f"🔧 Enabled providers: {', '.join(cls.AI_PROVIDERS)}")

        if errors:
            logger.error("❌ Configuration check failed:")
            logger.info("Please check your .env file and configuration.")
            return False
        
        logger.info("✅ All required configurations are valid")
        return True


logger.info(f"*" * 30 + " CONFIG START " + "*" * 30)
logger.info(f"GITHUB_TOKENS: {len(Config.GITHUB_TOKENS)} tokens")
logger.info(f"DATA_PATH: {Config.DATA_PATH}")
logger.info(f"PROXY_LIST: {len(Config.PROXY_LIST)} proxies configured")
logger.info(f"GEMINI_BALANCER_URL: {Config.GEMINI_BALANCER_URL or 'Not configured'}")
logger.info(f"GEMINI_BALANCER_AUTH: {'Configured' if Config.GEMINI_BALANCER_AUTH else 'Not configured'}")
logger.info(f"GEMINI_BALANCER_SYNC_ENABLED: {Config.parse_bool(Config.GEMINI_BALANCER_SYNC_ENABLED)}")
logger.info(f"GPT_LOAD_SYNC_ENABLED: {Config.parse_bool(Config.GPT_LOAD_SYNC_ENABLED)}")
logger.info(f"GPT_LOAD_URL: {Config.GPT_LOAD_URL or 'Not configured'}")
logger.info(f"GPT_LOAD_AUTH: {'Configured' if Config.GPT_LOAD_AUTH else 'Not configured'}")
logger.info(f"GPT_LOAD_GROUP_NAME: {Config.GPT_LOAD_GROUP_NAME or 'Not configured'}")
logger.info(f"AI_PROVIDERS_CONFIG: {len(Config.AI_PROVIDERS_CONFIG)} providers configured")
logger.info(f"DEFAULT_PROVIDER: {Config.DEFAULT_PROVIDER}")
logger.info(f"ENABLED_PROVIDERS: {', '.join(Config.AI_PROVIDERS)}")
logger.info(f"VALID_KEY_PREFIX: {Config.VALID_KEY_PREFIX}")
logger.info(f"RATE_LIMITED_KEY_PREFIX: {Config.RATE_LIMITED_KEY_PREFIX}")
logger.info(f"KEYS_SEND_PREFIX: {Config.KEYS_SEND_PREFIX}")
logger.info(f"VALID_KEY_DETAIL_PREFIX: {Config.VALID_KEY_DETAIL_PREFIX}")
logger.info(f"RATE_LIMITED_KEY_DETAIL_PREFIX: {Config.RATE_LIMITED_KEY_DETAIL_PREFIX}")
logger.info(f"KEYS_SEND_DETAIL_PREFIX: {Config.KEYS_SEND_DETAIL_PREFIX}")
logger.info(f"DATE_RANGE_DAYS: {Config.DATE_RANGE_DAYS} days")
logger.info(f"QUERIES_FILE: {Config.QUERIES_FILE}")
logger.info(f"SCANNED_SHAS_FILE: {Config.SCANNED_SHAS_FILE}")
logger.info(f"HAJIMI_CHECK_MODEL: {Config.HAJIMI_CHECK_MODEL}")
logger.info(f"FILE_PATH_BLACKLIST: {len(Config.FILE_PATH_BLACKLIST)} items")
logger.info(f"*" * 30 + " CONFIG END " + "*" * 30)

# 创建全局配置实例
config = Config()
