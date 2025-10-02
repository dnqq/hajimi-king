"""
启动 Web Dashboard

运行: python start_web.py
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.Logger import logger

def init_database():
    """初始化数据库（如果需要）"""
    from common.config import config
    from web.models import Base, engine, SystemConfig
    from web.database import SessionLocal
    from utils.config_loader import config_loader

    db_path = os.path.join(config.DATA_PATH, "hajimi_king.db")
    db_exists = os.path.exists(db_path)

    # 如果数据库文件不存在，创建表结构
    if not db_exists:
        logger.info("🔧 Database not found, creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created")

    # 检查是否需要添加默认供应商
    providers = config_loader.get_ai_providers()

    if not providers:
        logger.info("🔧 No providers found, adding defaults...")

        # 默认供应商配置
        default_providers = [
            {
                "name": "gemini",
                "type": "gemini",
                "check_model": "gemini-2.0-flash-exp",
                "api_endpoint": "generativelanguage.googleapis.com",
                "key_patterns": ["AIzaSy[A-Za-z0-9\\-_]{33}"],
                "gpt_load_group_name": "",
                "skip_ai_analysis": True
            },
            {
                "name": "openai",
                "type": "openai_style",
                "check_model": "gpt-3.5-turbo",
                "api_base_url": "https://api.openai.com/v1",
                "key_patterns": ["sk-[A-Za-z0-9\\-_]{20,100}"],
                "gpt_load_group_name": "",
                "skip_ai_analysis": False
            }
        ]

        # 写入 system_config 表
        db = SessionLocal()
        try:
            config_entry = db.query(SystemConfig).filter_by(key='ai_providers').first()
            if config_entry:
                config_entry.value = default_providers
            else:
                config_entry = SystemConfig(
                    key='ai_providers',
                    value=default_providers,
                    description='AI Provider Configurations'
                )
                db.add(config_entry)
            db.commit()
            logger.info("✅ Default providers (Gemini, OpenAI) added")
        except Exception as e:
            logger.error(f"❌ Failed to add default providers: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        logger.info(f"✅ Database ready with {len(providers)} provider(s)")

def main():
    """启动 Web 服务"""
    logger.info("=" * 60)
    logger.info("🌐 Starting Hajimi King Web Dashboard")
    logger.info("=" * 60)

    # 初始化数据库
    init_database()

    import uvicorn
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=8787,
        reload=False,  # 生产模式，禁用自动重载
        log_level="info"
    )

if __name__ == "__main__":
    main()
