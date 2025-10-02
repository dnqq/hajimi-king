"""
启动 Web Dashboard

运行: python start_web.py
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.Logger import logger

def main():
    """启动 Web 服务"""
    logger.info("=" * 60)
    logger.info("🌐 Starting Hajimi King Web Dashboard")
    logger.info("=" * 60)

    import uvicorn
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式，自动重载
        log_level="info"
    )

if __name__ == "__main__":
    main()
