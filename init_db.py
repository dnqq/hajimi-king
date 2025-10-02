"""
数据库初始化脚本

运行: python init_db.py
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.database import init_db, DATABASE_PATH, SessionLocal
from web.models import SystemConfig
from common.Logger import logger

def add_default_providers():
    """添加默认供应商配置"""
    db = SessionLocal()
    try:
        # 检查是否已有供应商配置
        existing_config = db.query(SystemConfig).filter(SystemConfig.key == 'ai_providers').first()

        if existing_config:
            logger.info("⏩ AI providers config already exists, skipping default setup")
            return

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

        # 保存到数据库
        config = SystemConfig(
            key='ai_providers',
            value=default_providers,
            description='AI 供应商配置（默认：Gemini + OpenAI）'
        )
        db.add(config)
        db.commit()

        logger.info("✅ Added default AI providers: Gemini, OpenAI")

    except Exception as e:
        logger.error(f"❌ Failed to add default providers: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """初始化数据库"""
    logger.info("=" * 60)
    logger.info("🗄️  Initializing SQLite Database")
    logger.info("=" * 60)

    # 创建数据库
    init_db()

    # 添加默认供应商
    add_default_providers()

    logger.info(f"📁 Database location: {DATABASE_PATH}")
    logger.info("✅ Database initialization complete!")
    logger.info("=" * 60)

    # 显示提示信息
    print("\n💡 Next steps:")
    print("1. Add ENCRYPTION_KEY to .env file (check logs above)")
    print("2. Run: python -m app.hajimi_king")
    print("3. Run: uvicorn web.main:app --reload")
    print("4. Visit: http://localhost:8000\n")

if __name__ == "__main__":
    main()
