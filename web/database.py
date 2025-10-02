"""
数据库连接和会话管理
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from common.config import config

# 数据库文件路径
DATABASE_PATH = os.path.join(config.DATA_PATH, "hajimi_king.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # 允许多线程访问
        "timeout": 15  # 写入超时等待 15 秒
    },
    echo=False,  # 生产环境关闭 SQL 日志
    pool_pre_ping=True  # 连接池健康检查
)

# 启用 WAL 模式（读写并发）
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")  # 性能优化
    cursor.execute("PRAGMA cache_size=10000")  # 缓存优化
    cursor.execute("PRAGMA temp_store=MEMORY")  # 临时表放内存
    cursor.close()

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 基类
Base = declarative_base()

def get_db():
    """
    依赖注入：获取数据库会话
    用于 FastAPI 路由
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    初始化数据库：创建所有表
    """
    from web.models import APIKey, ScannedFile, ScanTask, SyncLog, SystemConfig, DailyStat
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized at: {DATABASE_PATH}")
