"""
数据库操作管理器（替代 file_manager）
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from common.Logger import logger
from web.models import APIKey, ScannedFile, ScanTask, SyncLog, DailyStat
from web.database import SessionLocal
from utils.crypto import key_encryption


class DBManager:
    """数据库操作管理器"""

    @staticmethod
    def save_api_key(
        api_key: str,
        provider: str,
        status: str,
        source_repo: str,
        source_file_path: str,
        source_file_url: str,
        source_file_sha: str,
        gpt_load_group_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[APIKey]:
        """
        保存 API 密钥到数据库

        Returns:
            APIKey 对象，如果密钥已存在则返回 None
        """
        db = SessionLocal()
        try:
            # 1. 生成哈希值（用于去重）
            key_hash = key_encryption.hash_key(api_key)

            # 2. 检查是否已存在
            existing_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
            if existing_key:
                logger.info(f"🔄 Key already exists: {api_key[:10]}... (provider: {provider})")
                return None

            # 3. 加密密钥
            key_encrypted = key_encryption.encrypt_key(api_key)

            # 4. 创建记录
            db_key = APIKey(
                key_hash=key_hash,
                key_encrypted=key_encrypted,
                provider=provider,
                status=status,
                source_repo=source_repo,
                source_file_path=source_file_path,
                source_file_url=source_file_url,
                source_file_sha=source_file_sha,
                gpt_load_group_name=gpt_load_group_name,
                extra_data=metadata or {},
                discovered_at=datetime.utcnow(),
                last_validated_at=datetime.utcnow() if status in ['valid', 'rate_limited'] else None
            )

            db.add(db_key)
            db.commit()
            db.refresh(db_key)

            logger.info(f"💾 Saved new key to DB: {api_key[:10]}... (id: {db_key.id}, provider: {provider}, status: {status})")
            return db_key

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save key to DB: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def is_file_scanned(file_sha: str) -> bool:
        """检查文件是否已扫描"""
        db = SessionLocal()
        try:
            exists = db.query(ScannedFile).filter(ScannedFile.file_sha == file_sha).first() is not None
            return exists
        finally:
            db.close()

    @staticmethod
    def mark_file_scanned(
        file_sha: str,
        repo: str,
        file_path: str,
        file_url: str,
        keys_found: int = 0,
        valid_keys_count: int = 0,
        repo_pushed_at: Optional[datetime] = None
    ) -> ScannedFile:
        """标记文件为已扫描"""
        db = SessionLocal()
        try:
            scanned_file = ScannedFile(
                file_sha=file_sha,
                repo=repo,
                file_path=file_path,
                file_url=file_url,
                keys_found=keys_found,
                valid_keys_count=valid_keys_count,
                repo_pushed_at=repo_pushed_at,
                scanned_at=datetime.utcnow()
            )

            db.add(scanned_file)
            db.commit()
            db.refresh(scanned_file)

            return scanned_file
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark file as scanned: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def get_pending_sync_keys(
        target: str,  # 'balancer' or 'gpt_load'
        limit: int = 100
    ) -> List[APIKey]:
        """获取待同步的密钥"""
        db = SessionLocal()
        try:
            query = db.query(APIKey).filter(APIKey.status == 'valid')

            if target == 'balancer':
                query = query.filter(APIKey.synced_to_balancer == False)
            elif target == 'gpt_load':
                query = query.filter(APIKey.synced_to_gpt_load == False)

            keys = query.limit(limit).all()
            return keys
        finally:
            db.close()

    @staticmethod
    def mark_key_synced(key_id: int, target: str, success: bool = True, error_message: Optional[str] = None):
        """标记密钥为已同步"""
        db = SessionLocal()
        try:
            db_key = db.query(APIKey).filter(APIKey.id == key_id).first()
            if not db_key:
                return

            # 更新同步状态
            if target == 'balancer':
                db_key.synced_to_balancer = success
            elif target == 'gpt_load':
                db_key.synced_to_gpt_load = success

            # 记录同步日志
            sync_log = SyncLog(
                key_id=key_id,
                target_service=target,
                group_name=db_key.gpt_load_group_name if target == 'gpt_load' else None,
                status='success' if success else 'failed',
                error_message=error_message,
                synced_at=datetime.utcnow()
            )

            db.add(sync_log)
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark key as synced: {e}")
        finally:
            db.close()

    @staticmethod
    def get_stats_summary() -> Dict[str, int]:
        """获取统计摘要"""
        db = SessionLocal()
        try:
            total_keys = db.query(func.count(APIKey.id)).scalar() or 0
            valid_keys = db.query(func.count(APIKey.id)).filter(APIKey.status == 'valid').scalar() or 0
            rate_limited_keys = db.query(func.count(APIKey.id)).filter(APIKey.status == 'rate_limited').scalar() or 0
            invalid_keys = db.query(func.count(APIKey.id)).filter(APIKey.status == 'invalid').scalar() or 0
            pending_keys = db.query(func.count(APIKey.id)).filter(APIKey.status == 'pending').scalar() or 0

            # 今日新增
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_keys = db.query(func.count(APIKey.id)).filter(APIKey.discovered_at >= today_start).scalar() or 0

            # 待同步
            pending_balancer_sync = db.query(func.count(APIKey.id)).filter(
                and_(APIKey.status == 'valid', APIKey.synced_to_balancer == False)
            ).scalar() or 0

            pending_gpt_load_sync = db.query(func.count(APIKey.id)).filter(
                and_(APIKey.status == 'valid', APIKey.synced_to_gpt_load == False)
            ).scalar() or 0

            return {
                'total_keys': total_keys,
                'valid_keys': valid_keys,
                'rate_limited_keys': rate_limited_keys,
                'invalid_keys': invalid_keys,
                'pending_keys': pending_keys,
                'today_keys': today_keys,
                'pending_balancer_sync': pending_balancer_sync,
                'pending_gpt_load_sync': pending_gpt_load_sync
            }
        finally:
            db.close()


# 全局实例
db_manager = DBManager()
