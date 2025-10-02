"""
扫描管理 API
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from web.database import get_db
from web.models import ScanTask, ScannedFile
from web.schemas import ScanTaskResponse

router = APIRouter()


@router.get("/tasks", response_model=List[ScanTaskResponse])
async def list_scan_tasks(limit: int = 20, db: Session = Depends(get_db)):
    """
    获取扫描任务列表
    """
    tasks = db.query(ScanTask).order_by(desc(ScanTask.started_at)).limit(limit).all()
    return tasks


@router.get("/stats")
async def get_scan_stats(db: Session = Depends(get_db)):
    """
    获取扫描统计
    """
    from sqlalchemy import func

    total_files_scanned = db.query(func.count(ScannedFile.id)).scalar() or 0
    total_keys_found = db.query(func.sum(ScannedFile.keys_found)).scalar() or 0
    total_valid_keys = db.query(func.sum(ScannedFile.valid_keys_count)).scalar() or 0

    return {
        "total_files_scanned": total_files_scanned,
        "total_keys_found": total_keys_found,
        "total_valid_keys": total_valid_keys
    }


@router.get("/recent-files", response_model=List[dict])
async def get_recent_scanned_files(limit: int = 20, db: Session = Depends(get_db)):
    """
    获取最近扫描的文件
    """
    files = db.query(ScannedFile).order_by(desc(ScannedFile.scanned_at)).limit(limit).all()

    result = []
    for file in files:
        result.append({
            "id": file.id,
            "repo": file.repo,
            "file_path": file.file_path,
            "file_url": file.file_url,
            "keys_found": file.keys_found,
            "valid_keys_count": file.valid_keys_count,
            "scanned_at": file.scanned_at
        })

    return result
