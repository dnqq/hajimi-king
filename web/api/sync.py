"""
同步管理 API
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from common.Logger import logger
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
    from common.config import config
    from web.models import APIKey
    from sqlalchemy import func, and_

    # 时间范围
    from datetime import datetime, timedelta
    time_24h = datetime.utcnow() - timedelta(hours=24)

    # Balancer 统计
    # 24小时内同步成功的数量
    balancer_synced_24h = db.query(func.count(SyncLog.id)).filter(
        SyncLog.target_service == 'gemini_balancer',
        SyncLog.status == 'success',
        SyncLog.synced_at >= time_24h
    ).scalar() or 0

    # 总共已同步的数量（状态为valid且已同步到balancer）
    total_balancer_synced = db.query(func.count(APIKey.id)).filter(
        APIKey.synced_to_balancer == True
    ).scalar() or 0

    # GPT Load 统计
    # 24小时内同步成功的数量
    gpt_load_synced_24h = db.query(func.count(SyncLog.id)).filter(
        SyncLog.target_service == 'gpt_load',
        SyncLog.status == 'success',
        SyncLog.synced_at >= time_24h
    ).scalar() or 0

    # 总共已同步的数量（状态为valid且已同步到gpt_load）
    total_gpt_load_synced = db.query(func.count(APIKey.id)).filter(
        APIKey.synced_to_gpt_load == True
    ).scalar() or 0

    # 获取待同步密钥数量（不限制数量）
    # Balancer: 只有启用时才统计
    if config.GEMINI_BALANCER_SYNC_ENABLED:
        pending_balancer_count = db.query(func.count(APIKey.id)).filter(
            and_(APIKey.status == 'valid', APIKey.synced_to_balancer == False)
        ).scalar() or 0
    else:
        pending_balancer_count = 0

    # GPT Load: 只统计配置了 gpt_load_group_name 的 provider
    if config.GPT_LOAD_SYNC_ENABLED:
        # 获取所有有效未同步的 key
        pending_keys = db.query(APIKey).filter(
            and_(APIKey.status == 'valid', APIKey.synced_to_gpt_load == False)
        ).all()

        # 实时检查每个 key 的 provider 是否配置了 group_name
        from app.providers.config_key_extractor import ConfigKeyExtractor
        pending_gpt_load_count = 0
        for key in pending_keys:
            group_name = ConfigKeyExtractor.get_gpt_load_group_name(key.provider)
            if group_name and group_name.strip():
                pending_gpt_load_count += 1
    else:
        pending_gpt_load_count = 0

    return {
        "balancer": {
            "pending_count": pending_balancer_count,
            "total_synced": total_balancer_synced,
            "synced_24h": balancer_synced_24h
        },
        "gpt_load": {
            "pending_count": pending_gpt_load_count,
            "total_synced": total_gpt_load_synced,
            "synced_24h": gpt_load_synced_24h
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
                result = sync_utils._send_balancer_worker([decrypted_key])
                if result == "success":
                    db_manager.mark_key_synced(key_obj.id, 'balancer', success=True)
                    success_count += 1
                else:
                    db_manager.mark_key_synced(key_obj.id, 'balancer', success=False, error_message=result)
                    fail_count += 1

            elif target == 'gpt_load':
                # 实时获取 group_name（支持动态修改配置）
                from app.providers.config_key_extractor import ConfigKeyExtractor
                group_name = ConfigKeyExtractor.get_gpt_load_group_name(key_obj.provider)

                # 检查是否配置了 group_name
                if not group_name or not group_name.strip():
                    logger.warning(f"⚠️ Skipping key {key_obj.id}: provider '{key_obj.provider}' has no gpt_load_group_name configured")
                    fail_count += 1
                    continue

                result = sync_utils._send_gpt_load_worker([decrypted_key], group_name)
                if result == "success":
                    db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=True)
                    success_count += 1
                else:
                    db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=False, error_message=result)
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
