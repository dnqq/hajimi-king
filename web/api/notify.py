"""
通知功能 API
支持 Webhook 通知
"""
import os
import requests
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.database import get_db
from common.Logger import logger
from common.config import config

router = APIRouter()

# 通知配置
WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")
NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "false").lower() in ("true", "1", "yes")


def send_webhook_notification(title: str, message: str, data: Optional[dict] = None):
    """
    发送 Webhook 通知

    Args:
        title: 通知标题
        message: 通知内容
        data: 附加数据
    """
    if not NOTIFY_ENABLED or not WEBHOOK_URL:
        logger.debug("Notifications disabled or webhook URL not configured")
        return False

    try:
        payload = {
            "title": title,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }

        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            logger.info(f"✅ Webhook notification sent: {title}")
            return True
        else:
            logger.error(f"❌ Webhook notification failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to send webhook notification: {e}")
        return False


@router.get("/config")
async def get_notify_config():
    """
    获取通知配置
    """
    return {
        "enabled": NOTIFY_ENABLED,
        "webhook_configured": bool(WEBHOOK_URL)
    }


@router.post("/test")
async def test_notification():
    """
    测试通知
    """
    from datetime import datetime

    result = send_webhook_notification(
        title="Hajimi King 测试通知",
        message="这是一条测试通知，如果您收到此消息，说明通知功能正常工作。",
        data={
            "test": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    if result:
        return {"success": True, "message": "Test notification sent successfully"}
    else:
        return {"success": False, "message": "Failed to send test notification"}


# 在发现有效密钥时调用的函数（供挖掘程序使用）
def notify_valid_key_found(provider: str, key_preview: str, source_repo: str):
    """
    通知发现有效密钥

    Args:
        provider: 供应商
        key_preview: 密钥预览
        source_repo: 来源仓库
    """
    send_webhook_notification(
        title=f"🎉 发现有效 {provider.upper()} 密钥",
        message=f"来自仓库: {source_repo}",
        data={
            "provider": provider,
            "key_preview": key_preview,
            "source_repo": source_repo
        }
    )


# 每日统计报告（可以通过定时任务调用）
def send_daily_report(stats: dict):
    """
    发送每日统计报告

    Args:
        stats: 统计数据
    """
    message = f"""
📊 Hajimi King 每日报告

总密钥数: {stats.get('total_keys', 0)}
有效密钥: {stats.get('valid_keys', 0)}
今日新增: {stats.get('today_keys', 0)}
待同步: {stats.get('pending_sync', 0)}
"""

    send_webhook_notification(
        title="📈 Hajimi King 每日统计报告",
        message=message.strip(),
        data=stats
    )
