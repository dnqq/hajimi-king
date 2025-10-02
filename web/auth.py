"""
简单的密钥身份验证
通过 .env 文件中的 WEB_ACCESS_KEY 控制访问
"""
import os
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from common.config import config
from common.Logger import logger

# 安全方案
security = HTTPBearer()

# 从环境变量读取访问密钥
WEB_ACCESS_KEY = os.getenv("WEB_ACCESS_KEY", "")

# 如果没有配置密钥，发出警告
if not WEB_ACCESS_KEY:
    logger.warning("=" * 60)
    logger.warning("⚠️  WEB_ACCESS_KEY not set in .env")
    logger.warning("⚠️  Web Dashboard is UNPROTECTED!")
    logger.warning("⚠️  Add this to your .env file:")
    logger.warning("WEB_ACCESS_KEY=your_secret_key_here")
    logger.warning("=" * 60)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> bool:
    """
    验证访问令牌

    Args:
        credentials: HTTP Authorization 头中的凭证

    Returns:
        bool: 验证通过返回 True

    Raises:
        HTTPException: 验证失败抛出 401 错误
    """
    # 如果未配置密钥，允许所有访问（开发模式）
    if not WEB_ACCESS_KEY:
        return True

    # 验证令牌
    if credentials.credentials != WEB_ACCESS_KEY:
        logger.warning(f"❌ Invalid access key attempt: {credentials.credentials[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def get_optional_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[str]:
    """
    可选的令牌验证（用于页面访问）

    Returns:
        Optional[str]: 返回令牌或 None
    """
    if credentials:
        return credentials.credentials
    return None
