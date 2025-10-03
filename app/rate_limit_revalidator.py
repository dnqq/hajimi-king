"""
限流密钥重新校验器
每天自动重新验证标记为 rate_limited 的密钥
"""
import time
from datetime import datetime, timedelta
from typing import List

from common.Logger import logger
from utils.db_manager import db_manager
from utils.crypto import key_encryption
from app.providers.config_based_factory import ConfigBasedAIProviderFactory


class RateLimitRevalidator:
    """限流密钥重新校验器"""

    def __init__(self):
        self.last_run_time = None

    def revalidate_rate_limited_keys(self, batch_size: int = 50):
        """
        重新验证所有限流密钥

        Args:
            batch_size: 每批次处理的密钥数量
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info(f"🔄 Starting rate-limited keys revalidation at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 获取所有限流密钥
            rate_limited_keys = self._get_rate_limited_keys()

            if not rate_limited_keys:
                logger.info("✅ No rate-limited keys found, nothing to revalidate")
                return

            total_keys = len(rate_limited_keys)
            logger.info(f"📊 Found {total_keys} rate-limited keys to revalidate")

            # 统计结果
            stats = {
                'total': total_keys,
                'valid': 0,
                'still_rate_limited': 0,
                'invalid': 0,
                'error': 0
            }

            # 分批处理
            for i in range(0, total_keys, batch_size):
                batch = rate_limited_keys[i:i + batch_size]
                logger.info(f"📦 Processing batch {i // batch_size + 1}/{(total_keys + batch_size - 1) // batch_size}")

                for key_obj in batch:
                    try:
                        result = self._revalidate_single_key(key_obj)
                        stats[result] += 1

                        # 避免过快触发限流
                        time.sleep(2)

                    except Exception as e:
                        logger.error(f"❌ Error revalidating key {key_obj.id}: {e}")
                        stats['error'] += 1

                # 批次间休息
                if i + batch_size < total_keys:
                    logger.info(f"💤 Batch complete, sleeping 30 seconds...")
                    time.sleep(30)

            # 输出统计
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info("=" * 60)
            logger.info("📊 Revalidation Complete - Summary:")
            logger.info(f"   Total Processed: {stats['total']}")
            logger.info(f"   ✅ Now Valid: {stats['valid']}")
            logger.info(f"   ⚠️ Still Rate Limited: {stats['still_rate_limited']}")
            logger.info(f"   ❌ Now Invalid: {stats['invalid']}")
            logger.info(f"   ⚠️ Errors: {stats['error']}")
            logger.info(f"   ⏱️ Duration: {duration:.2f} seconds")
            logger.info("=" * 60)

            self.last_run_time = end_time

        except Exception as e:
            logger.error(f"❌ Revalidation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _get_rate_limited_keys(self) -> List:
        """获取所有限流密钥"""
        from web.models import APIKey
        from web.database import get_db

        db = next(get_db())
        try:
            keys = db.query(APIKey).filter(
                APIKey.status == 'rate_limited'
            ).all()
            return keys
        finally:
            db.close()

    def _revalidate_single_key(self, key_obj) -> str:
        """
        重新验证单个密钥

        Returns:
            'valid', 'still_rate_limited', 'invalid', 'error'
        """
        try:
            # 解密密钥
            decrypted_key = key_encryption.decrypt_key(key_obj.key_encrypted)

            # 获取供应商
            provider = ConfigBasedAIProviderFactory.get_provider_by_name(key_obj.provider)
            if not provider:
                logger.warning(f"⚠️ Provider '{key_obj.provider}' not found for key {key_obj.id}")
                return 'error'

            # 重新验证
            logger.info(f"🔍 Revalidating {key_obj.provider} key {key_obj.id}: {decrypted_key[:20]}...")
            validation_result = provider.validate_key(decrypted_key)

            # 更新状态
            new_status = None
            if validation_result == "ok":
                new_status = 'valid'
                result_type = 'valid'
                logger.info(f"✅ Key {key_obj.id} is now VALID!")
            elif "rate_limited" in validation_result.lower():
                new_status = 'rate_limited'
                result_type = 'still_rate_limited'
                logger.warning(f"⚠️ Key {key_obj.id} is still RATE LIMITED")
            else:
                new_status = 'invalid'
                result_type = 'invalid'
                logger.info(f"❌ Key {key_obj.id} is now INVALID: {validation_result}")

            # 更新数据库
            if new_status:
                db_manager.update_key_status(
                    key_id=key_obj.id,
                    status=new_status,
                    metadata={'last_revalidation': datetime.utcnow().isoformat(), 'validation_result': validation_result}
                )

                # 如果变为有效，会被同步线程自动处理（无需手动触发）
                if new_status == 'valid':
                    logger.info(f"✅ Key {key_obj.id} recovered to valid, will be synced by sync worker")

            return result_type

        except Exception as e:
            logger.error(f"❌ Failed to revalidate key {key_obj.id}: {e}")
            return 'error'


# 全局实例
rate_limit_revalidator = RateLimitRevalidator()
