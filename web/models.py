"""
SQLAlchemy ORM 模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from web.database import Base, engine

# 导出供外部使用
__all__ = ['Base', 'engine', 'APIKey', 'ScannedFile', 'ScanTask', 'SyncLog', 'SystemConfig', 'DailyStat', 'AIProvider']


class APIKey(Base):
    """API 密钥表"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 密钥信息（加密存储）
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA256 哈希用于去重
    key_encrypted = Column(Text, nullable=False)  # 加密后的密钥

    # 供应商信息
    provider = Column(String(50), nullable=False, index=True)  # gemini, openai, cerebras, etc.
    status = Column(String(20), nullable=False, default='pending', index=True)  # valid, rate_limited, invalid, pending

    # 来源信息
    source_repo = Column(String(255), index=True)  # github 仓库名：user/repo
    source_file_path = Column(Text)  # 文件路径
    source_file_url = Column(Text)  # GitHub URL
    source_file_sha = Column(String(64), index=True)  # 文件 SHA

    # 时间戳
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_validated_at = Column(DateTime)

    # 同步状态
    synced_to_balancer = Column(Boolean, default=False, index=True)
    synced_to_gpt_load = Column(Boolean, default=False, index=True)
    gpt_load_group_name = Column(String(100))  # GPT Load 分组名

    # 元数据（JSON 格式存储灵活数据）
    extra_data = Column(JSON, default={})  # 验证历史、错误信息等（避免使用 metadata 保留字）

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    sync_logs = relationship("SyncLog", back_populates="api_key", cascade="all, delete-orphan")

    # 复合索引
    __table_args__ = (
        Index('idx_provider_status', 'provider', 'status'),
        Index('idx_sync_status', 'status', 'synced_to_balancer', 'synced_to_gpt_load'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, provider={self.provider}, status={self.status})>"


class ScannedFile(Base):
    """已扫描文件表（用于去重）"""
    __tablename__ = "scanned_files"

    id = Column(Integer, primary_key=True, autoincrement=True)

    file_sha = Column(String(64), unique=True, nullable=False, index=True)  # 文件 SHA（唯一）
    repo = Column(String(255), nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    file_url = Column(Text)

    # 统计信息
    keys_found = Column(Integer, default=0)  # 发现的密钥总数
    valid_keys_count = Column(Integer, default=0)  # 有效密钥数

    # 时间戳
    scanned_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # 文件元数据
    repo_pushed_at = Column(DateTime)  # 仓库最后更新时间
    extra_data = Column(JSON, default={})

    def __repr__(self):
        return f"<ScannedFile(repo={self.repo}, file_path={self.file_path})>"


class ScanTask(Base):
    """扫描任务表（查询执行历史）"""
    __tablename__ = "scan_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    query_text = Column(Text, nullable=False)  # GitHub 搜索查询

    # 执行结果
    status = Column(String(20), nullable=False, index=True)  # running, completed, failed
    files_scanned = Column(Integer, default=0)
    keys_found = Column(Integer, default=0)
    valid_keys_count = Column(Integer, default=0)

    # 时间
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # 错误信息
    error_message = Column(Text)
    extra_data = Column(JSON, default={})

    def __repr__(self):
        return f"<ScanTask(id={self.id}, query={self.query_text[:50]}, status={self.status})>"


class SyncLog(Base):
    """同步日志表"""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    key_id = Column(Integer, ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False, index=True)

    target_service = Column(String(50), nullable=False, index=True)  # gemini_balancer, gpt_load
    group_name = Column(String(100))  # GPT Load 分组

    status = Column(String(20), nullable=False, index=True)  # success, failed
    error_message = Column(Text)

    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    extra_data = Column(JSON, default={})

    # 关系
    api_key = relationship("APIKey", back_populates="sync_logs")

    def __repr__(self):
        return f"<SyncLog(key_id={self.key_id}, service={self.target_service}, status={self.status})>"


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_config"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)  # JSON 格式存储配置值
    description = Column(Text)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig(key={self.key})>"


class DailyStat(Base):
    """每日统计表"""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)

    date = Column(DateTime, nullable=False, index=True)  # 统计日期
    provider = Column(String(50), index=True)  # 供应商

    # 统计数据
    keys_discovered = Column(Integer, default=0)
    valid_keys_count = Column(Integer, default=0)
    rate_limited_count = Column(Integer, default=0)
    invalid_keys_count = Column(Integer, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_date_provider', 'date', 'provider', unique=True),
    )

    def __repr__(self):
        return f"<DailyStat(date={self.date}, provider={self.provider})>"


class AIProvider(Base):
    """AI 供应商配置表（独立表，替代 system_config 中的 JSON 存储）"""
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    name = Column(String(50), unique=True, nullable=False, index=True)  # 供应商名称（唯一）
    type = Column(String(50), nullable=False)  # gemini, openai_style

    # 模型配置
    check_model = Column(String(100), nullable=False)  # 验证使用的模型
    api_endpoint = Column(String(255))  # Gemini: API endpoint
    api_base_url = Column(String(255))  # OpenAI Style: base URL

    # 密钥匹配
    key_patterns = Column(JSON, nullable=False)  # 正则表达式列表

    # 同步配置
    gpt_load_group_name = Column(String(100))  # GPT Load 分组名

    # 功能开关
    skip_ai_analysis = Column(Boolean, default=False)  # 跳过 AI 分析
    enabled = Column(Boolean, default=True, index=True)  # 是否启用

    # 自定义搜索关键字
    custom_keywords = Column(JSON, default=[])  # 自定义搜索关键字列表

    # 排序
    sort_order = Column(Integer, default=0)  # 显示顺序

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AIProvider(id={self.id}, name={self.name}, type={self.type})>"

    def to_dict(self):
        """转换为字典格式（兼容旧 API）"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "check_model": self.check_model,
            "api_endpoint": self.api_endpoint,
            "api_base_url": self.api_base_url,
            "key_patterns": self.key_patterns or [],
            "gpt_load_group_name": self.gpt_load_group_name,
            "skip_ai_analysis": self.skip_ai_analysis,
            "enabled": self.enabled,
            "custom_keywords": self.custom_keywords or [],
            "sort_order": self.sort_order,
        }
