"""
配置管理（简化版 - 只从数据库加载业务配置）
"""
import os
import random
from typing import Dict, Optional, List

from dotenv import load_dotenv

from common.Logger import logger

# 只在环境变量不存在时才从.env加载值
load_dotenv(override=False)


class Config:
    """配置类"""

    def __init__(self):
        self._config_loader = None
        self._cache = {}  # 配置缓存
        self._cache_timestamp = {}  # 缓存时间戳

    @property
    def config_loader(self):
        """延迟导入 config_loader（避免循环依赖）"""
        if self._config_loader is None:
            try:
                from utils.config_loader import config_loader
                self._config_loader = config_loader
            except Exception as e:
                logger.warning(f"⚠️ Failed to load config_loader: {e}")
                self._config_loader = None
        return self._config_loader

    def reload_config(self):
        """重新加载配置（清除缓存）"""
        self._cache.clear()
        self._cache_timestamp.clear()
        if self._config_loader:
            self._config_loader._cache.clear()
            self._config_loader._cache_timestamp.clear()
        logger.info("✅ Configuration reloaded")

    # ========== 核心配置（从 .env 读取）==========

    @property
    def DATA_PATH(self) -> str:
        """数据路径"""
        return os.getenv('DATA_PATH', os.path.join(os.getcwd(), 'data'))

    @property
    def ENCRYPTION_KEY(self) -> str:
        """加密密钥（用于加密数据库中的 API Key）"""
        return os.getenv('ENCRYPTION_KEY', '')

    # ========== 业务配置（从数据库读取）==========

    @property
    def GITHUB_TOKENS(self) -> List[str]:
        """GitHub Tokens（从数据库读取）"""
        if self.config_loader:
            github_config = self.config_loader.get_github_config()
            return github_config.get('tokens', [])
        return []

    @property
    def PROXY_LIST(self) -> List[str]:
        """代理列表（从数据库读取）"""
        if self.config_loader:
            github_config = self.config_loader.get_github_config()
            return github_config.get('proxy', [])
        return []

    @property
    def AI_PROVIDERS_CONFIG(self) -> List[Dict]:
        """AI 供应商配置（从数据库读取）"""
        if self.config_loader:
            return self.config_loader.get_ai_providers()
        return []

    @property
    def AI_PROVIDERS(self) -> List[str]:
        """启用的供应商名称列表"""
        return [provider.get('name') for provider in self.AI_PROVIDERS_CONFIG]

    @property
    def DEFAULT_PROVIDER(self) -> str:
        """默认供应商"""
        providers = self.AI_PROVIDERS
        return providers[0] if providers else "gemini"

    # ========== 同步配置（从数据库读取）==========

    @property
    def GEMINI_BALANCER_SYNC_ENABLED(self) -> bool:
        """Gemini Balancer 是否启用"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gemini_balancer_enabled', False)
        return False

    @property
    def GEMINI_BALANCER_URL(self) -> str:
        """Gemini Balancer URL"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gemini_balancer_url', '')
        return ''

    @property
    def GEMINI_BALANCER_AUTH(self) -> str:
        """Gemini Balancer Auth"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gemini_balancer_auth', '')
        return ''

    @property
    def GPT_LOAD_SYNC_ENABLED(self) -> bool:
        """GPT Load 是否启用"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gpt_load_enabled', False)
        return False

    @property
    def GPT_LOAD_URL(self) -> str:
        """GPT Load URL"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gpt_load_url', '')
        return ''

    @property
    def GPT_LOAD_AUTH(self) -> str:
        """GPT Load Auth"""
        if self.config_loader:
            sync_config = self.config_loader.get_sync_config()
            return sync_config.get('gpt_load_auth', '')
        return ''

    # ========== 搜索配置（从数据库读取）==========

    @property
    def DATE_RANGE_DAYS(self) -> int:
        """日期范围过滤（天数）"""
        if self.config_loader:
            search_config = self.config_loader.get_search_config()
            return search_config.get('date_range_days', 730)
        return 730

    @property
    def FILE_PATH_BLACKLIST(self) -> List[str]:
        """文件路径黑名单"""
        if self.config_loader:
            search_config = self.config_loader.get_search_config()
            return search_config.get('file_path_blacklist', [])
        return ['readme', 'docs', 'doc/', '.md', 'example', 'sample', 'tutorial', 'test', 'spec', 'demo', 'mock']

    # ========== AI 分析配置（从数据库读取）==========

    @property
    def AI_ANALYSIS_ENABLED(self) -> bool:
        """AI 分析是否启用"""
        if self.config_loader:
            ai_config = self.config_loader.get_ai_analysis_config()
            return ai_config.get('enabled', False)
        return False

    @property
    def AI_ANALYSIS_URL(self) -> str:
        """AI 分析 API URL"""
        if self.config_loader:
            ai_config = self.config_loader.get_ai_analysis_config()
            return ai_config.get('url', '')
        return ''

    @property
    def AI_ANALYSIS_MODEL(self) -> str:
        """AI 分析模型"""
        if self.config_loader:
            ai_config = self.config_loader.get_ai_analysis_config()
            return ai_config.get('model', 'gpt-4o-mini')
        return 'gpt-4o-mini'

    @property
    def AI_ANALYSIS_API_KEY(self) -> str:
        """AI 分析 API Key"""
        if self.config_loader:
            ai_config = self.config_loader.get_ai_analysis_config()
            return ai_config.get('api_key', '')
        return ''

    # ========== 固定配置（不需要修改）==========

    @property
    def QUERIES_FILE(self) -> str:
        """查询文件路径"""
        return "queries.txt"

    @property
    def SCANNED_SHAS_FILE(self) -> str:
        """已扫描 SHA 文件"""
        return "scanned_shas.txt"

    @property
    def HAJIMI_CHECK_MODEL(self) -> str:
        """Hajimi 检查模型"""
        return "gemini-2.0-flash-exp"

    # ========== 工具方法 ==========

    @classmethod
    def parse_bool(cls, value: str) -> bool:
        """解析布尔值"""
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value = value.strip().lower()
            return value in ('true', '1', 'yes', 'on', 'enabled')

        if isinstance(value, int):
            return bool(value)

        return False

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """随机获取代理"""
        if not self.PROXY_LIST:
            return None

        proxy_url = random.choice(self.PROXY_LIST)
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def check(self) -> bool:
        """
        检查必要的配置是否存在
        在数据库模式下，只检查核心配置
        """
        # 检查核心配置
        if not self.ENCRYPTION_KEY:
            logger.error("❌ ENCRYPTION_KEY not configured in .env")
            return False

        # 检查数据路径
        if not os.path.exists(self.DATA_PATH):
            logger.info(f"📁 Creating data directory: {self.DATA_PATH}")
            os.makedirs(self.DATA_PATH, exist_ok=True)

        logger.info("✅ Core configuration check passed")
        logger.info("💡 Business configurations (GitHub tokens, AI providers) are loaded from database")
        return True


# 全局配置实例
config = Config()
