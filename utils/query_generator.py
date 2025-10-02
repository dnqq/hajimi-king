import os
import re
from typing import List, Set, Dict
from common.config import config
from common.Logger import logger


class QueryGenerator:
    """根据供应商配置自动生成GitHub搜索查询"""

    @staticmethod
    def extract_search_prefix(pattern: str) -> str:
        """
        从正则表达式中提取可搜索的前缀

        Examples:
            AIzaSy[A-Za-z0-9\\-_]{33} -> AIzaSy
            sk-[A-Za-z0-9\\-_]{20,100} -> sk-
            sk-or-v1-[A-Za-z0-9\\-_]{20,100} -> sk-or-v1-
            csk-[A-Za-z0-9\\-_]{20,100} -> csk-

        Args:
            pattern: 正则表达式模式

        Returns:
            str: 提取的前缀，如果无法提取则返回空字符串
        """
        # 清理转义字符
        pattern = pattern.replace('\\\\', '\\')

        # 提取固定前缀部分（直到第一个正则元字符）
        match = re.match(r'^([A-Za-z0-9\-_]+)', pattern)
        if match:
            prefix = match.group(1)
            # 至少3个字符才有搜索意义
            if len(prefix) >= 3:
                return prefix

        return ""

    @staticmethod
    def generate_queries_from_config() -> List[str]:
        """
        从供应商配置自动生成搜索查询

        三层查询策略：
        1. 精准前缀查询（针对稀有格式的 key）
        2. 通用文件查询（覆盖多种 key 的常见文件）
        3. 智能组合查询（提高覆盖率）

        Returns:
            List[str]: 自动生成的查询列表
        """
        queries = []
        all_prefixes = set()
        provider_prefix_map = {}  # 记录每个前缀属于哪个供应商

        # === 收集所有供应商的前缀 ===
        for provider_config in config.AI_PROVIDERS_CONFIG:
            provider_name = provider_config.get('name', 'unknown')
            key_patterns = provider_config.get('key_patterns', [])

            for pattern in key_patterns:
                prefix = QueryGenerator.extract_search_prefix(pattern)

                if prefix and len(prefix) >= 3:
                    all_prefixes.add(prefix)
                    provider_prefix_map[prefix] = provider_name

        logger.info(f"🔍 Detected {len(all_prefixes)} unique key prefixes from {len(config.AI_PROVIDERS_CONFIG)} providers")
        for prefix, provider in provider_prefix_map.items():
            logger.info(f"   - {prefix} ({provider})")

        # === 第一层：精准前缀查询 ===
        # 为每个前缀生成基础搜索
        for prefix in sorted(all_prefixes):
            queries.append(f'"{prefix}" in:file')

        logger.info(f"✅ Generated {len(all_prefixes)} prefix-based queries")

        # === 第二层：通用配置文件查询 ===
        # 这些文件通常包含多种 API key，一次搜索可以提取所有供应商的 key
        common_file_queries = [
            'filename:.env',
            'filename:.env.example',
            'filename:config.json',
            'filename:credentials.json',
            'filename:secrets.json',
            'path:config/ extension:json',
        ]
        queries.extend(common_file_queries)

        logger.info(f"✅ Added {len(common_file_queries)} common file queries")

        # === 第三层：智能组合查询（可选，根据需要启用）===
        # 这些查询可以发现一些不常见的位置
        # 注释掉以避免过多查询，可以在 queries.txt 中手动添加
        # smart_queries = [
        #     'api_key in:file filename:.env',
        #     '"API_KEY=" in:file',
        #     'path:src/config/',
        # ]
        # queries.extend(smart_queries)

        logger.info(f"🎯 Total auto-generated queries: {len(queries)}")
        return queries

    @staticmethod
    def load_manual_queries(queries_file: str) -> List[str]:
        """
        加载手动定义的查询

        支持：
        - 以 # 开头的注释行
        - 空行
        - 正常的查询语句

        Args:
            queries_file: 查询文件路径

        Returns:
            List[str]: 手动查询列表
        """
        queries = []

        if not os.path.exists(queries_file):
            logger.info(f"📋 Manual queries file not found: {queries_file}")
            return queries

        try:
            with open(queries_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # 跳过注释和空行
                    if not line or line.startswith('#'):
                        continue

                    queries.append(line)

            logger.info(f"📋 Loaded {len(queries)} manual queries from {queries_file}")

        except Exception as e:
            logger.error(f"❌ Failed to load manual queries from {queries_file}: {e}")

        return queries

    @staticmethod
    def normalize_query(query: str) -> str:
        """
        标准化查询用于去重

        处理逻辑：
        1. 移除多余空格
        2. 保留引号内容的原始顺序
        3. 对非引号部分进行排序

        Args:
            query: 原始查询字符串

        Returns:
            str: 标准化后的查询字符串
        """
        # 移除多余空格
        query = " ".join(query.split())

        # 分离引号内容和其他部分
        parts = []
        i = 0
        while i < len(query):
            if query[i] == '"':
                # 找到配对的引号
                end_quote = query.find('"', i + 1)
                if end_quote != -1:
                    parts.append(query[i:end_quote + 1])
                    i = end_quote + 1
                else:
                    parts.append(query[i])
                    i += 1
            elif query[i] == ' ':
                i += 1
            else:
                # 提取非引号的词
                start = i
                while i < len(query) and query[i] not in (' ', '"'):
                    i += 1
                parts.append(query[start:i])

        # 对部分进行排序（引号内容保持原样）
        return " ".join(sorted(parts))

    @staticmethod
    def merge_queries(auto_queries: List[str], manual_queries: List[str]) -> List[str]:
        """
        合并自动生成和手动查询，去重并保留手动查询优先级

        逻辑：
        1. 手动查询优先（放在前面）
        2. 自动查询补充（去除与手动重复的）

        Args:
            auto_queries: 自动生成的查询列表
            manual_queries: 手动定义的查询列表

        Returns:
            List[str]: 合并后的查询列表
        """
        seen = set()
        merged = []

        # 统计信息
        manual_count = 0
        auto_count = 0
        duplicate_count = 0

        # 先添加手动查询（标准化后去重）
        for query in manual_queries:
            normalized = QueryGenerator.normalize_query(query)
            if normalized not in seen:
                seen.add(normalized)
                merged.append(query)
                manual_count += 1
            else:
                duplicate_count += 1

        # 再添加自动查询（跳过重复的）
        for query in auto_queries:
            normalized = QueryGenerator.normalize_query(query)
            if normalized not in seen:
                seen.add(normalized)
                merged.append(query)
                auto_count += 1
            else:
                duplicate_count += 1

        logger.info(f"✅ Merged queries: {manual_count} manual + {auto_count} auto = {len(merged)} total")
        if duplicate_count > 0:
            logger.info(f"   ℹ️  Skipped {duplicate_count} duplicate queries")

        return merged

    @staticmethod
    def get_query_statistics(queries: List[str]) -> Dict[str, int]:
        """
        统计查询的类型分布

        Args:
            queries: 查询列表

        Returns:
            Dict[str, int]: 统计信息
        """
        stats = {
            'total': len(queries),
            'prefix_based': 0,
            'filename_based': 0,
            'path_based': 0,
            'content_based': 0,
            'other': 0
        }

        for query in queries:
            query_lower = query.lower()

            if 'in:file' in query_lower and '"' in query:
                stats['prefix_based'] += 1
            elif 'filename:' in query_lower:
                stats['filename_based'] += 1
            elif 'path:' in query_lower:
                stats['path_based'] += 1
            elif any(keyword in query_lower for keyword in ['api_key', 'secret', 'token']):
                stats['content_based'] += 1
            else:
                stats['other'] += 1

        return stats


# 全局实例
query_generator = QueryGenerator()
