"""
密钥加密工具
"""
import hashlib
import os
import base64
from cryptography.fernet import Fernet
from common.Logger import logger


class KeyEncryption:
    """密钥加密/解密工具"""

    def __init__(self):
        # 从环境变量读取加密密钥
        encryption_key = os.getenv('ENCRYPTION_KEY')

        if not encryption_key:
            # 首次运行：生成新密钥
            encryption_key = Fernet.generate_key().decode()
            logger.warning("=" * 60)
            logger.warning("⚠️  ENCRYPTION_KEY not found in .env")
            logger.warning("⚠️  Generated new encryption key:")
            logger.warning(f"ENCRYPTION_KEY={encryption_key}")
            logger.warning("⚠️  Please add this to your .env file!")
            logger.warning("=" * 60)

        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise

    def encrypt_key(self, api_key: str) -> str:
        """
        加密密钥

        Args:
            api_key: 明文密钥

        Returns:
            加密后的密钥（Base64 编码）
        """
        try:
            encrypted = self.cipher.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt key: {e}")
            raise

    def decrypt_key(self, encrypted_key: str) -> str:
        """
        解密密钥

        Args:
            encrypted_key: 加密后的密钥

        Returns:
            明文密钥
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt key: {e}")
            raise

    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        生成密钥哈希（用于去重）

        Args:
            api_key: 明文密钥

        Returns:
            SHA256 哈希值（十六进制）
        """
        return hashlib.sha256(api_key.encode()).hexdigest()


# 全局实例
key_encryption = KeyEncryption()
