"""
同步管理 API
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from web.database import get_db
from web.models import SyncLog
from web.schemas import SyncLogResponse

router = APIRouter()


@router.get("/logs", response_model=List[SyncLogResponse])
async def list_sync_logs(limit: int = 50, db: Session = Depends(get_db)):
    """
    获取同步日志列表
    """
    logs = db.query(SyncLog).order_by(desc(SyncLog.synced_at)).limit(limit).all()
    return logs


@router.get("/status")
async def get_sync_status(db: Session = Depends(get_db)):
    """
    获取同步状态
    """
    from utils.db_manager import db_manager

    # 获取待同步密钥
    pending_balancer = db_manager.get_pending_sync_keys('balancer', limit=10)
    pending_gpt_load = db_manager.get_pending_sync_keys('gpt_load', limit=10)

    # 最近同步统计
    from sqlalchemy import func
    from datetime import datetime, timedelta

    recent_time = datetime.utcnow() - timedelta(hours=1)

    recent_balancer_success = db.query(func.count(SyncLog.id)).filter(
        SyncLog.target_service == 'gemini_balancer',
        SyncLog.status == 'success',
        SyncLog.synced_at >= recent_time
    ).scalar() or 0

    recent_gpt_load_success = db.query(func.count(SyncLog.id)).filter(
        SyncLog.target_service == 'gpt_load',
        SyncLog.status == 'success',
        SyncLog.synced_at >= recent_time
    ).scalar() or 0

    return {
        "balancer": {
            "pending_count": len(pending_balancer),
            "recent_synced": recent_balancer_success
        },
        "gpt_load": {
            "pending_count": len(pending_gpt_load),
            "recent_synced": recent_gpt_load_success
        }
    }


@router.post("/trigger/{target}")
async def trigger_sync(target: str):
    """
    手动触发同步
    """
    from utils.sync_utils import sync_utils
    from utils.db_manager import db_manager
    from common.config import config

    if target not in ['balancer', 'gpt_load']:
        return {"success": False, "message": "Invalid target"}

    # 检查是否启用同步
    if target == 'balancer':
        if not sync_utils.balancer_enabled:
            return {"success": False, "message": "Balancer sync not enabled in config"}
    elif target == 'gpt_load':
        if not config.parse_bool(config.GPT_LOAD_SYNC_ENABLED):
            return {"success": False, "message": "GPT Load sync not enabled in config"}

    # 获取待同步密钥
    pending_keys = db_manager.get_pending_sync_keys(target, limit=100)

    if not pending_keys:
        return {"success": True, "message": "No keys to sync", "count": 0}

    # 执行同步
    success_count = 0
    fail_count = 0

    for key_obj in pending_keys:
        from utils.crypto import key_encryption
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

            # 根据目标执行同步
            if target == 'balancer':
                result = sync_utils._sync_to_balancer([decrypted_key])
                if result:
                    db_manager.mark_key_synced(key_obj.id, 'balancer', success=True)
                    success_count += 1
                else:
                    db_manager.mark_key_synced(key_obj.id, 'balancer', success=False, error_message="Sync failed")
                    fail_count += 1

            elif target == 'gpt_load':
                result = sync_utils._sync_to_gpt_load([decrypted_key], key_obj.provider, key_obj.gpt_load_group_name)
                if result:
                    db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=True)
                    success_count += 1
                else:
                    db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=False, error_message="Sync failed")
                    fail_count += 1

        except Exception as e:
            logger.error(f"Failed to sync key {key_obj.id}: {e}")
            db_manager.mark_key_synced(key_obj.id, target, success=False, error_message=str(e))
            fail_count += 1

    return {
        "success": True,
        "message": f"Sync completed",
        "total": len(pending_keys),
        "success_count": success_count,
        "fail_count": fail_count
    }
