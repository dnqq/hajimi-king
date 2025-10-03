"""
统计分析 API
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from web.database import get_db
from web.models import APIKey, DailyStat, ScannedFile
from web.schemas import StatsSummary, ProviderStat, DailyStatResponse

router = APIRouter()


@router.get("/summary")
async def get_stats_summary(db: Session = Depends(get_db)):
    """
    获取统计摘要（带趋势对比：昨日、上周、上月）
    """
    from utils.db_manager import db_manager
    from sqlalchemy import case

    # 获取基础统计
    stats = db_manager.get_stats_summary()

    now = datetime.utcnow()

    # 时间范围定义
    yesterday_start = now - timedelta(days=2)
    yesterday_end = now - timedelta(days=1)

    week_ago_start = now - timedelta(days=14)
    week_ago_end = now - timedelta(days=7)

    month_ago_start = now - timedelta(days=60)
    month_ago_end = now - timedelta(days=30)

    # 查询历史数据
    # 昨日总数
    yesterday_total = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < yesterday_end
    ).scalar() or 0

    # 上周总数
    week_ago_total = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < week_ago_end
    ).scalar() or 0

    # 上月总数
    month_ago_total = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < month_ago_end
    ).scalar() or 0

    # 昨日有效密钥数
    yesterday_valid = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < yesterday_end,
        APIKey.status == 'valid'
    ).scalar() or 0

    # 上周有效密钥数
    week_ago_valid = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < week_ago_end,
        APIKey.status == 'valid'
    ).scalar() or 0

    # 上月有效密钥数
    month_ago_valid = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < month_ago_end,
        APIKey.status == 'valid'
    ).scalar() or 0

    # 昨日限流密钥数
    yesterday_rate_limited = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < yesterday_end,
        APIKey.status == 'rate_limited'
    ).scalar() or 0

    # 上周限流密钥数
    week_ago_rate_limited = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < week_ago_end,
        APIKey.status == 'rate_limited'
    ).scalar() or 0

    # 上月限流密钥数
    month_ago_rate_limited = db.query(func.count(APIKey.id)).filter(
        APIKey.discovered_at < month_ago_end,
        APIKey.status == 'rate_limited'
    ).scalar() or 0

    # 当前数据
    current_total = stats.get('total_keys', 0)
    current_valid = stats.get('valid_keys', 0)
    current_rate_limited = stats.get('rate_limited_keys', 0)

    # 添加趋势数据
    stats['trends'] = {
        # 总密钥数趋势
        'total_keys_day': _calculate_change_rate(current_total, yesterday_total),
        'total_keys_week': _calculate_change_rate(current_total, week_ago_total),
        'total_keys_month': _calculate_change_rate(current_total, month_ago_total),

        # 有效密钥趋势
        'valid_keys_day': _calculate_change_rate(current_valid, yesterday_valid),
        'valid_keys_week': _calculate_change_rate(current_valid, week_ago_valid),
        'valid_keys_month': _calculate_change_rate(current_valid, month_ago_valid),

        # 限流密钥趋势
        'rate_limited_keys_day': _calculate_change_rate(current_rate_limited, yesterday_rate_limited),
        'rate_limited_keys_week': _calculate_change_rate(current_rate_limited, week_ago_rate_limited),
        'rate_limited_keys_month': _calculate_change_rate(current_rate_limited, month_ago_rate_limited),
    }

    return stats


def _calculate_change_rate(current: int, previous: int) -> dict:
    """计算变化率和趋势"""
    if previous == 0:
        if current > 0:
            return {'rate': 100.0, 'direction': 'up', 'value': current - previous}
        return {'rate': 0.0, 'direction': 'neutral', 'value': 0}

    change = current - previous
    rate = (change / previous) * 100
    direction = 'up' if change > 0 else ('down' if change < 0 else 'neutral')

    return {
        'rate': round(abs(rate), 1),
        'direction': direction,
        'value': change
    }


@router.get("/providers", response_model=List[ProviderStat])
async def get_provider_stats(db: Session = Depends(get_db)):
    """
    获取各供应商统计
    """
    from sqlalchemy import case

    try:
        results = db.query(
            APIKey.provider,
            func.count(APIKey.id).label('total_keys'),
            func.sum(case((APIKey.status == 'valid', 1), else_=0)).label('valid_keys'),
            func.sum(case((APIKey.status == 'rate_limited', 1), else_=0)).label('rate_limited_keys'),
            func.sum(case((APIKey.status == 'invalid', 1), else_=0)).label('invalid_keys')
        ).group_by(APIKey.provider).all()

        stats = []
        for row in results:
            valid_keys = int(row.valid_keys) if row.valid_keys else 0
            total_keys = int(row.total_keys) if row.total_keys else 0
            rate_limited = int(row.rate_limited_keys) if row.rate_limited_keys else 0
            invalid = int(row.invalid_keys) if row.invalid_keys else 0

            valid_rate = (valid_keys / total_keys * 100) if total_keys > 0 else 0

            stats.append({
                "provider": row.provider,
                "total_keys": total_keys,
                "valid_keys": valid_keys,
                "rate_limited_keys": rate_limited,
                "invalid_keys": invalid,
                "valid_rate": round(valid_rate, 2)
            })

        return stats
    except Exception as e:
        # 返回空列表而不是抛出异常
        return []


@router.get("/daily", response_model=List[dict])
async def get_daily_stats(days: int = 7, db: Session = Depends(get_db)):
    """
    获取每日统计（最近 N 天）
    """
    from sqlalchemy import case

    start_date = datetime.utcnow() - timedelta(days=days)

    # 按日期和供应商分组统计
    try:
        results = db.query(
            func.date(APIKey.discovered_at).label('date'),
            APIKey.provider,
            func.count(APIKey.id).label('keys_discovered'),
            func.sum(case((APIKey.status == 'valid', 1), else_=0)).label('valid_keys_count'),
            func.sum(case((APIKey.status == 'rate_limited', 1), else_=0)).label('rate_limited_count'),
            func.sum(case((APIKey.status == 'invalid', 1), else_=0)).label('invalid_keys_count')
        ).filter(
            APIKey.discovered_at >= start_date
        ).group_by(
            func.date(APIKey.discovered_at),
            APIKey.provider
        ).order_by(
            desc(func.date(APIKey.discovered_at))
        ).all()

        stats = []
        for row in results:
            stats.append({
                "date": row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                "provider": row.provider,
                "keys_discovered": int(row.keys_discovered) if row.keys_discovered else 0,
                "valid_keys_count": int(row.valid_keys_count) if row.valid_keys_count else 0,
                "rate_limited_count": int(row.rate_limited_count) if row.rate_limited_count else 0,
                "invalid_keys_count": int(row.invalid_keys_count) if row.invalid_keys_count else 0
            })

        return stats
    except Exception as e:
        # 返回空列表而不是抛出异常
        return []


@router.get("/top-repos", response_model=List[dict])
async def get_top_repos(limit: int = 10, db: Session = Depends(get_db)):
    """
    获取 Top N 密钥来源仓库
    """
    from sqlalchemy import case

    try:
        results = db.query(
            APIKey.source_repo,
            func.count(APIKey.id).label('total_keys'),
            func.sum(case((APIKey.status == 'valid', 1), else_=0)).label('valid_keys')
        ).filter(
            APIKey.source_repo.isnot(None)
        ).group_by(
            APIKey.source_repo
        ).order_by(
            desc(func.count(APIKey.id))
        ).limit(limit).all()

        repos = []
        for row in results:
            repos.append({
                "repo": row.source_repo,
                "total_keys": int(row.total_keys) if row.total_keys else 0,
                "valid_keys": int(row.valid_keys) if row.valid_keys else 0
            })

        return repos
    except Exception as e:
        return []


@router.get("/recent-keys", response_model=List[dict])
async def get_recent_keys(limit: int = 10, db: Session = Depends(get_db)):
    """
    获取最近发现的密钥（简化版）
    """
    from utils.crypto import key_encryption

    keys = db.query(APIKey).order_by(desc(APIKey.discovered_at)).limit(limit).all()

    result = []
    for key in keys:
        try:
            decrypted = key_encryption.decrypt_key(key.key_encrypted)
            key_preview = decrypted[:8] + "****"
        except:
            key_preview = "ERROR"

        result.append({
            "id": key.id,
            "provider": key.provider,
            "status": key.status,
            "key_preview": key_preview,
            "source_repo": key.source_repo,
            "discovered_at": key.discovered_at
        })

    return result


@router.get("/provider-validity-trend", response_model=List[dict])
async def get_provider_validity_trend(days: int = 30, db: Session = Depends(get_db)):
    """
    获取供应商有效率趋势（按天统计）
    """
    from sqlalchemy import case

    start_date = datetime.utcnow() - timedelta(days=days)

    try:
        # 按日期和供应商统计有效率
        results = db.query(
            func.date(APIKey.discovered_at).label('date'),
            APIKey.provider,
            func.count(APIKey.id).label('total_keys'),
            func.sum(case((APIKey.status == 'valid', 1), else_=0)).label('valid_keys')
        ).filter(
            APIKey.discovered_at >= start_date
        ).group_by(
            func.date(APIKey.discovered_at),
            APIKey.provider
        ).order_by(
            func.date(APIKey.discovered_at)
        ).all()

        # 计算有效率
        trend_data = []
        for row in results:
            total = int(row.total_keys) if row.total_keys else 0
            valid = int(row.valid_keys) if row.valid_keys else 0
            valid_rate = (valid / total * 100) if total > 0 else 0

            trend_data.append({
                "date": row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                "provider": row.provider,
                "total_keys": total,
                "valid_keys": valid,
                "valid_rate": round(valid_rate, 2)
            })

        return trend_data
    except Exception as e:
        return []
