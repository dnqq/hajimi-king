"""
Telegram 通知工具
"""
import requests
from typing import Optional
from common.Logger import logger


class TelegramNotifier:
    """Telegram 通知器"""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        发送 Telegram 消息

        Args:
            message: 消息内容
            parse_mode: 解析模式（HTML, Markdown, None）

        Returns:
            bool: 是否发送成功
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("⚠️ Telegram bot_token or chat_id not configured")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ Telegram message sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False

    def send_test_message(self) -> bool:
        """发送测试消息"""
        return self.send_message(
            "🧪 <b>测试消息</b>\n\n"
            "如果你收到这条消息，说明 Telegram 配置成功！\n\n"
            "✅ 哈基米系统"
        )

    @staticmethod
    def validate_config(bot_token: str, chat_id: str) -> tuple[bool, str]:
        """
        验证 Telegram 配置

        Returns:
            (bool, str): (是否有效, 错误信息)
        """
        if not bot_token or not bot_token.strip():
            return False, "Bot Token 不能为空"

        if not chat_id or not chat_id.strip():
            return False, "Chat ID 不能为空"

        # 测试连接
        notifier = TelegramNotifier(bot_token, chat_id)
        if notifier.send_test_message():
            return True, "配置有效"
        else:
            return False, "无法发送测试消息，请检查 Bot Token 和 Chat ID"


# 全局实例
telegram_notifier = None


def get_telegram_notifier():
    """获取全局 Telegram 通知器实例"""
    global telegram_notifier

    if telegram_notifier is None:
        # 从数据库加载配置
        try:
            from web.database import SessionLocal
            from web.models import SystemConfig

            db = SessionLocal()
            try:
                telegram_config = db.query(SystemConfig).filter(
                    SystemConfig.key == "telegram_config"
                ).first()

                if telegram_config and telegram_config.value:
                    config = telegram_config.value
                    bot_token = config.get('bot_token', '')
                    chat_id = config.get('chat_id', '')

                    if bot_token and chat_id:
                        telegram_notifier = TelegramNotifier(bot_token, chat_id)
                        logger.info("✅ Telegram notifier initialized from config")
                    else:
                        logger.warning("⚠️ Telegram config incomplete")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"❌ Failed to load Telegram config: {e}")

    return telegram_notifier


def reload_telegram_notifier():
    """重新加载 Telegram 通知器配置"""
    global telegram_notifier
    telegram_notifier = None
    return get_telegram_notifier()
