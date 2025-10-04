"""
时间工具类 - 统一使用上海时间
"""
from datetime import datetime
import pytz

# 上海时区
SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')


def now_shanghai():
    """获取当前上海时间"""
    return datetime.now(SHANGHAI_TZ)


def utc_to_shanghai(utc_time: datetime) -> datetime:
    """将UTC时间转换为上海时间"""
    if utc_time is None:
        return None

    # 如果时间没有时区信息，假定为UTC
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)

    return utc_time.astimezone(SHANGHAI_TZ)


def shanghai_to_utc(shanghai_time: datetime) -> datetime:
    """将上海时间转换为UTC时间"""
    if shanghai_time is None:
        return None

    # 如果时间没有时区信息，假定为上海时间
    if shanghai_time.tzinfo is None:
        shanghai_time = SHANGHAI_TZ.localize(shanghai_time)

    return shanghai_time.astimezone(pytz.utc)
