"""
同步监控 - 检测超过24小时未同步完成的有效密钥并发送Telegram通知
"""
from datetime import datetime, timedelta
from common.Logger import logger
from utils.time_utils import now_shanghai
from web.database import SessionLocal
from web.models import APIKey
from sqlalchemy import and_


class SyncMonitor:
    """同步监控器"""

    @staticmethod
    def check_and_notify():
        """检查超过24小时未同步完成的密钥并通知"""
        db = SessionLocal()
        try:
            # 计算24小时前的时间（上海时间）
            threshold_time = now_shanghai().replace(tzinfo=None) - timedelta(hours=24)

            # 查找超过24小时未同步的有效密钥
            unsync_keys = db.query(APIKey).filter(
                and_(
                    APIKey.status == 'valid',
                    APIKey.discovered_at < threshold_time,
                    APIKey.synced_to_balancer == False,
                    APIKey.synced_to_gpt_load == False
                )
            ).all()

            if unsync_keys:
                count = len(unsync_keys)
                logger.warning(f"⚠️ Found {count} valid keys not synced for over 24 hours")

                # 发送Telegram通知
                SyncMonitor._send_telegram_notification(count, unsync_keys)
            else:
                logger.info("✅ All valid keys are synced or within 24 hours")

        except Exception as e:
            logger.error(f"❌ Failed to check sync status: {e}")
        finally:
            db.close()

    @staticmethod
    def _send_telegram_notification(count: int, keys: list):
        """发送Telegram通知"""
        try:
            from utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()
            if not notifier:
                logger.warning("⚠️ Telegram notifier not configured, skipping notification")
                return

            # 按供应商分组统计
            provider_stats = {}
            for key in keys:
                provider = key.provider
                if provider not in provider_stats:
                    provider_stats[provider] = 0
                provider_stats[provider] += 1

            # 构建消息
            stats_text = "\n".join([
                f"• {provider}: {count}个密钥"
                for provider, count in provider_stats.items()
            ])

            message = (
                f"⚠️ <b>同步状态警告</b>\n\n"
                f"发现 <b>{count}</b> 个有效密钥超过24小时未同步：\n\n"
                f"{stats_text}\n\n"
                f"请检查同步配置或手动同步密钥。\n\n"
                f"📊 哈基米系统"
            )

            success = notifier.send_message(message)
            if success:
                logger.info(f"✅ Sent Telegram notification for {count} unsynced keys")
            else:
                logger.error("❌ Failed to send Telegram notification")

        except Exception as e:
            logger.error(f"❌ Failed to send Telegram notification: {e}")


# 全局实例
sync_monitor = SyncMonitor()
