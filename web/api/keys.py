"""
密钥管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from web.database import get_db
from web.models import APIKey
from web.schemas import APIKeyListItem, APIKeyResponse, APIKeyUpdate, PaginatedResponse, BatchUpdateProviderRequest
from utils.crypto import key_encryption
from common.Logger import logger

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_keys(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    provider: Optional[str] = Query(None, description="按供应商筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    sync_status: Optional[str] = Query(None, description="按同步状态筛选"),
    search: Optional[str] = Query(None, description="搜索仓库名或密钥"),
    db: Session = Depends(get_db)
):
    """
    获取密钥列表（分页）
    """
    query = db.query(APIKey)

    # 筛选条件
    if provider:
        query = query.filter(APIKey.provider == provider)

    if status:
        query = query.filter(APIKey.status == status)

    if sync_status:
        if sync_status == 'synced':
            query = query.filter(
                or_(APIKey.synced_to_balancer == True, APIKey.synced_to_gpt_load == True)
            )
        elif sync_status == 'not_synced':
            query = query.filter(
                and_(APIKey.synced_to_balancer == False, APIKey.synced_to_gpt_load == False)
            )

    if search:
        # 模糊查询：仓库名、文件路径、或解密后的密钥内容
        # 注意：搜索密钥内容需要解密所有 key，性能较低，但数据量不大时可接受
        search_pattern = f"%{search}%"

        # 先按仓库名和文件路径过滤（高效）
        filtered_keys = query.filter(
            or_(
                APIKey.source_repo.ilike(search_pattern),
                APIKey.source_file_path.ilike(search_pattern)
            )
        ).all()

        # 如果搜索词像是密钥片段（包含字母数字），也搜索密钥内容
        if any(c.isalnum() for c in search):
            # 获取所有未过滤的 keys，检查密钥内容
            all_keys = query.all()
            for key in all_keys:
                try:
                    decrypted = key_encryption.decrypt_key(key.key_encrypted)
                    if search.lower() in decrypted.lower():
                        if key not in filtered_keys:
                            filtered_keys.append(key)
                except Exception:
                    pass

        # 替换查询为过滤后的 ID 列表
        if filtered_keys:
            key_ids = [k.id for k in filtered_keys]
            query = db.query(APIKey).filter(APIKey.id.in_(key_ids))
        else:
            # 没有匹配，返回空
            query = db.query(APIKey).filter(APIKey.id == -1)

    # 总数
    total = query.count()

    # 分页
    offset = (page - 1) * page_size
    keys = query.order_by(desc(APIKey.discovered_at)).offset(offset).limit(page_size).all()

    # 转换为列表项（脱敏密钥）
    items = []
    for key in keys:
        try:
            # 解密密钥并脱敏
            decrypted = key_encryption.decrypt_key(key.key_encrypted)
            key_preview = decrypted[:8] + "****" if len(decrypted) > 8 else decrypted

            items.append({
                "id": key.id,
                "provider": key.provider,
                "status": key.status,
                "source_repo": key.source_repo,
                "discovered_at": key.discovered_at,
                "synced_to_balancer": key.synced_to_balancer,
                "synced_to_gpt_load": key.synced_to_gpt_load,
                "key_preview": key_preview
            })
        except Exception as e:
            logger.error(f"Failed to decrypt key {key.id}: {e}")
            items.append({
                "id": key.id,
                "provider": key.provider,
                "status": key.status,
                "source_repo": key.source_repo,
                "discovered_at": key.discovered_at,
                "synced_to_balancer": key.synced_to_balancer,
                "synced_to_gpt_load": key.synced_to_gpt_load,
                "key_preview": "ERROR"
            })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@router.get("/{key_id}", response_model=dict)
async def get_key_detail(key_id: int, db: Session = Depends(get_db)):
    """
    获取密钥详情（包含完整密钥）
    """
    key = db.query(APIKey).filter(APIKey.id == key_id).first()

    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    try:
        # 解密完整密钥
        decrypted_key = key_encryption.decrypt_key(key.key_encrypted)

        return {
            "id": key.id,
            "key": decrypted_key,  # 完整密钥
            "key_hash": key.key_hash,
            "provider": key.provider,
            "status": key.status,
            "source_repo": key.source_repo,
            "source_file_path": key.source_file_path,
            "source_file_url": key.source_file_url,
            "source_file_sha": key.source_file_sha,
            "discovered_at": key.discovered_at,
            "last_validated_at": key.last_validated_at,
            "synced_to_balancer": key.synced_to_balancer,
            "synced_to_gpt_load": key.synced_to_gpt_load,
            "gpt_load_group_name": key.gpt_load_group_name,
            "extra_data": key.extra_data,
            "created_at": key.created_at,
            "updated_at": key.updated_at
        }
    except Exception as e:
        logger.error(f"Failed to decrypt key {key_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt key")


@router.patch("/{key_id}")
async def update_key(key_id: int, update_data: APIKeyUpdate, db: Session = Depends(get_db)):
    """
    更新密钥状态
    """
    key = db.query(APIKey).filter(APIKey.id == key_id).first()

    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    # 更新字段
    if update_data.status is not None:
        key.status = update_data.status

    if update_data.synced_to_balancer is not None:
        key.synced_to_balancer = update_data.synced_to_balancer

    if update_data.synced_to_gpt_load is not None:
        key.synced_to_gpt_load = update_data.synced_to_gpt_load

    if update_data.extra_data is not None:
        key.extra_data = update_data.extra_data

    db.commit()
    db.refresh(key)

    return {"success": True, "message": "Key updated"}


@router.delete("/{key_id}")
async def delete_key(key_id: int, db: Session = Depends(get_db)):
    """
    删除密钥
    """
    key = db.query(APIKey).filter(APIKey.id == key_id).first()

    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    db.delete(key)
    db.commit()

    return {"success": True, "message": "Key deleted"}


@router.post("/batch-delete")
async def batch_delete_keys(key_ids: List[int], db: Session = Depends(get_db)):
    """
    批量删除密钥
    """
    deleted_count = db.query(APIKey).filter(APIKey.id.in_(key_ids)).delete(synchronize_session=False)
    db.commit()

    return {"success": True, "deleted_count": deleted_count}


@router.post("/batch-update-provider")
async def batch_update_provider(request: BatchUpdateProviderRequest, db: Session = Depends(get_db)):
    """
    批量更改供应商
    """
    updated_count = db.query(APIKey).filter(APIKey.id.in_(request.key_ids)).update(
        {"provider": request.provider},
        synchronize_session=False
    )
    db.commit()

    return {"success": True, "updated_count": updated_count}


@router.post("/batch-revalidate")
async def batch_revalidate(key_ids: List[int], db: Session = Depends(get_db)):
    """
    批量重新校验密钥
    """
    from app.providers.config_based_factory import ConfigBasedAIProviderFactory
    from utils.crypto import key_encryption

    keys = db.query(APIKey).filter(APIKey.id.in_(key_ids)).all()

    success_count = 0
    fail_count = 0

    for key_obj in keys:
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

            # 获取 provider
            provider = ConfigBasedAIProviderFactory.get_provider_by_name(key_obj.provider)
            if not provider:
                logger.error(f"Provider {key_obj.provider} not found for key {key_obj.id}")
                fail_count += 1
                continue

            # 校验密钥
            validation_result = provider.validate_key(decrypted_key)

            if validation_result and "ok" in validation_result:
                key_obj.status = 'valid'
                success_count += 1
            elif "rate_limited" in validation_result:
                key_obj.status = 'rate_limited'
                success_count += 1
            else:
                key_obj.status = 'invalid'
                success_count += 1

            key_obj.last_validated_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Failed to revalidate key {key_obj.id}: {e}")
            fail_count += 1

    db.commit()

    return {
        "success": True,
        "total": len(keys),
        "success_count": success_count,
        "fail_count": fail_count
    }


@router.post("/batch-sync")
async def batch_sync(key_ids: List[int], db: Session = Depends(get_db)):
    """
    批量同步密钥到 GPT Load
    """
    from utils.crypto import key_encryption
    from utils.sync_utils import sync_utils
    from utils.db_manager import db_manager
    from app.providers.config_key_extractor import ConfigKeyExtractor

    keys = db.query(APIKey).filter(APIKey.id.in_(key_ids)).all()

    success_count = 0
    fail_count = 0

    for key_obj in keys:
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

            # 实时获取 group_name
            group_name = ConfigKeyExtractor.get_gpt_load_group_name(key_obj.provider)

            if not group_name or not group_name.strip():
                logger.warning(f"⚠️ Skipping key {key_obj.id}: provider '{key_obj.provider}' has no gpt_load_group_name configured")
                fail_count += 1
                continue

            # 执行同步
            result = sync_utils._send_gpt_load_worker([decrypted_key], group_name)

            if result == "success":
                db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=True)
                success_count += 1
            else:
                db_manager.mark_key_synced(key_obj.id, 'gpt_load', success=False, error_message=result)
                fail_count += 1

        except Exception as e:
            logger.error(f"Failed to sync key {key_obj.id}: {e}")
            fail_count += 1

    return {
        "success": True,
        "total": len(keys),
        "success_count": success_count,
        "fail_count": fail_count
    }


@router.get("/export/csv")
async def export_keys_csv(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    导出密钥为 CSV（待实现）
    """
    # TODO: 实现 CSV 导出
    return {"message": "CSV export not implemented yet"}
