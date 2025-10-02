import os
from typing import List

from common.Logger import logger
from common.config import config


class FileManager:
    """文件管理器：负责加载查询配置"""

    def __init__(self, data_dir: str):
        """
        初始化FileManager

        Args:
            data_dir: 数据目录路径
        """
        logger.info("🔧 Initializing FileManager")

        self.data_dir = data_dir

        # 创建数据目录
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"Created data directory: {self.data_dir}")
        else:
            logger.info(f"Data directory exists: {self.data_dir}")

        # 加载搜索查询
        try:
            self._search_queries = self.load_search_queries(config.QUERIES_FILE)
            logger.info(f"✅ Loaded {len(self._search_queries)} search queries")
        except Exception as e:
            logger.error(f"❌ Failed to load search queries: {e}")
            self._search_queries = []

    def load_search_queries(self, queries_file: str) -> List[str]:
        """
        加载搜索查询列表

        Args:
            queries_file: 查询文件名（相对于data_dir）

        Returns:
            查询字符串列表
        """
        queries_path = os.path.join(self.data_dir, queries_file)

        if not os.path.exists(queries_path):
            logger.debug(f"Queries file not found: {queries_path} (using auto-generated queries)")
            return []

        try:
            with open(queries_path, 'r', encoding='utf-8') as f:
                queries = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]

            logger.info(f"📖 Loaded {len(queries)} manual queries from {queries_file}")
            return queries

        except Exception as e:
            logger.error(f"❌ Error loading queries from {queries_path}: {e}")
            return []

    def get_search_queries(self) -> List[str]:
        """
        获取搜索查询列表

        Returns:
            查询字符串列表
        """
        return self._search_queries


# 全局实例
file_manager = FileManager(config.DATA_PATH)
