"""
Hajimi King - 三线程版本
使用任务调度器实现搜索、校验、同步分离
"""
import os
import sys
import signal

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.Logger import logger
from common.config import config
from app.task_scheduler import task_scheduler
from web.database import init_db


def signal_handler(signum, frame):
    """处理退出信号"""
    logger.info("⛔ Received shutdown signal")
    task_scheduler.shutdown()
    sys.exit(0)


def main():
    logger.info("=" * 60)
    logger.info("🚀 HAJIMI KING STARTING (Threaded Mode)")
    logger.info("=" * 60)

    # 1. 检查配置
    if not config.check():
        logger.error("❌ Config check failed. Exiting...")
        sys.exit(1)

    # 2. 初始化数据库
    init_db()

    # 3. 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. 启动任务调度器
    task_scheduler.start()

    logger.info("=" * 60)
    logger.info("✅ System ready - All workers started")
    logger.info("=" * 60)

    # 5. 保持主线程运行
    try:
        signal.pause()  # 等待信号
    except AttributeError:
        # Windows 不支持 signal.pause()
        import time
        while True:
            time.sleep(1)


if __name__ == "__main__":
    main()
