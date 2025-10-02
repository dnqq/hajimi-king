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
    from web.models import Base, engine
    from utils.db_manager import DBManager

    db_path = os.path.join(config.DATA_PATH, "hajimi_king.db")

    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        logger.info("🔧 Database not found, initializing...")
        Base.metadata.create_all(bind=engine)

        # 添加默认供应商
        db_manager = DBManager()

        # Gemini
        db_manager.add_or_update_provider({
            "name": "gemini",
            "type": "gemini",
            "check_model": "gemini-2.0-flash-exp",
            "api_endpoint": "generativelanguage.googleapis.com",
            "key_patterns": ["AIzaSy[A-Za-z0-9\\-_]{33}"],
            "gpt_load_group_name": "",
            "skip_ai_analysis": True
        })

        # OpenAI
        db_manager.add_or_update_provider({
            "name": "openai",
            "type": "openai_style",
            "check_model": "gpt-3.5-turbo",
            "api_base_url": "https://api.openai.com/v1",
            "key_patterns": ["sk-[A-Za-z0-9\\-_]{20,100}"],
            "gpt_load_group_name": "",
            "skip_ai_analysis": False
        })

        logger.info("✅ Database initialized with default providers")
    else:
        logger.info("✅ Database exists, skipping initialization")

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
