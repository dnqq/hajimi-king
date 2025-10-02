"""
密钥导出 API
"""
import csv
import io
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from web.database import get_db
from web.models import APIKey
from utils.crypto import key_encryption
from common.Logger import logger

router = APIRouter()


@router.get("/csv")
async def export_keys_csv(
    provider: Optional[str] = Query(None, description="按供应商筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db)
):
    """
    导出密钥为 CSV 文件
    """
    query = db.query(APIKey)

    # 筛选条件
    if provider:
        query = query.filter(APIKey.provider == provider)
    if status:
        query = query.filter(APIKey.status == status)

    keys = query.all()

    # 创建 CSV 内容
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow([
        'ID', 'Provider', 'Key', 'Status', 'Source Repo',
        'Source File', 'Source URL', 'Discovered At',
        'Synced to Balancer', 'Synced to GPT Load', 'GPT Load Group'
    ])

    # 写入数据
    for key in keys:
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key.key_encrypted)

            writer.writerow([
                key.id,
                key.provider,
                decrypted_key,
                key.status,
                key.source_repo or '',
                key.source_file_path or '',
                key.source_file_url or '',
                key.discovered_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if key.synced_to_balancer else 'No',
                'Yes' if key.synced_to_gpt_load else 'No',
                key.gpt_load_group_name or ''
            ])
        except Exception as e:
            logger.error(f"Failed to export key {key.id}: {e}")

    # 返回 CSV 文件
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=hajimi_keys_export.csv"}
    )


@router.get("/json")
async def export_keys_json(
    provider: Optional[str] = Query(None, description="按供应商筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db)
):
    """
    导出密钥为 JSON 文件
    """
    query = db.query(APIKey)

    # 筛选条件
    if provider:
        query = query.filter(APIKey.provider == provider)
    if status:
        query = query.filter(APIKey.status == status)

    keys = query.all()

    # 构建 JSON 数据
    data = []
    for key in keys:
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key.key_encrypted)

            data.append({
                "id": key.id,
                "provider": key.provider,
                "key": decrypted_key,
                "status": key.status,
                "source_repo": key.source_repo,
                "source_file_path": key.source_file_path,
                "source_file_url": key.source_file_url,
                "discovered_at": key.discovered_at.isoformat(),
                "last_validated_at": key.last_validated_at.isoformat() if key.last_validated_at else None,
                "synced_to_balancer": key.synced_to_balancer,
                "synced_to_gpt_load": key.synced_to_gpt_load,
                "gpt_load_group_name": key.gpt_load_group_name,
                "extra_data": key.extra_data
            })
        except Exception as e:
            logger.error(f"Failed to export key {key.id}: {e}")

    # 返回 JSON 文件
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=hajimi_keys_export.json"}
    )
