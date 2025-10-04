"""
Rate Limit 监控 API
提供 GitHub API 配额使用情况的实时查询
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.database import get_db
from web.auth import verify_token

router = APIRouter()


@router.get("/rate_limit/status")
async def get_rate_limit_status(db: Session = Depends(get_db), _=Depends(verify_token)):
    """获取 Rate Limit 实时状态"""
    try:
        from app.rate_limit_monitor import rate_limit_monitor

        status = rate_limit_monitor.get_status_summary()

        return {
            "success": True,
            "data": status
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/rate_limit/tokens")
async def get_token_details(db: Session = Depends(get_db), _=Depends(verify_token)):
    """获取各个 Token 的详细配额信息"""
    try:
        from app.rate_limit_monitor import rate_limit_monitor

        if not rate_limit_monitor.tokens:
            return {
                "success": True,
                "data": {
                    "message": "No tokens registered yet. Search task hasn't started.",
                    "tokens": []
                }
            }

        token_details = []
        for token, status in rate_limit_monitor.tokens.items():
            token_details.append({
                "token_masked": status.token,
                "search_api": {
                    "limit": status.search_limit,
                    "remaining": status.search_remaining,
                    "usage_rate": f"{(1 - status.search_remaining / status.search_limit) * 100:.1f}%",
                    "reset_time": status.search_reset.isoformat() if status.search_reset else None,
                },
                "core_api": {
                    "limit": status.core_limit,
                    "remaining": status.core_remaining,
                    "usage_rate": f"{(1 - status.core_remaining / status.core_limit) * 100:.1f}%",
                    "reset_time": status.core_reset.isoformat() if status.core_reset else None,
                },
                "health": {
                    "score": f"{status.get_health_score():.2f}",
                    "is_healthy": status.is_healthy(),
                    "consecutive_errors": status.consecutive_errors,
                },
                "last_update": status.last_update.isoformat(),
            })

        return {
            "success": True,
            "data": {
                "total_tokens": len(rate_limit_monitor.tokens),
                "healthy_tokens": sum(1 for s in rate_limit_monitor.tokens.values() if s.is_healthy()),
                "tokens": token_details
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/rate_limit/schedule")
async def get_schedule_info(db: Session = Depends(get_db), _=Depends(verify_token)):
    """获取调度策略和下次执行时间"""
    import os
    from datetime import datetime, timedelta

    try:
        from app.rate_limit_monitor import rate_limit_monitor

        use_dynamic = os.getenv("DYNAMIC_SCHEDULING", "true").lower() == "true"

        if use_dynamic:
            next_interval = rate_limit_monitor.calculate_next_interval()
            next_run = datetime.now() + timedelta(seconds=next_interval)

            return {
                "success": True,
                "data": {
                    "mode": "dynamic",
                    "strategy": os.getenv("SCHEDULING_STRATEGY", "balanced"),
                    "next_interval_seconds": next_interval,
                    "next_interval_minutes": round(next_interval / 60, 1),
                    "next_run_time": next_run.isoformat(),
                    "config": {
                        "min_interval_minutes": rate_limit_monitor.min_interval_minutes,
                        "max_interval_minutes": rate_limit_monitor.max_interval_minutes,
                        "target_search_reserve": f"{rate_limit_monitor.target_search_reserve * 100:.0f}%",
                        "target_core_reserve": f"{rate_limit_monitor.target_core_reserve * 100:.0f}%",
                    },
                    "last_search": rate_limit_monitor.last_search_stats if rate_limit_monitor.last_search_stats else None
                }
            }
        else:
            # 固定时间调度
            next_run_hour = int(os.getenv("DAILY_RUN_HOUR", "3"))
            next_run = datetime.now().replace(hour=next_run_hour, minute=0, second=0)
            if next_run <= datetime.now():
                next_run += timedelta(days=1)

            return {
                "success": True,
                "data": {
                    "mode": "fixed",
                    "next_run_time": next_run.isoformat(),
                    "daily_run_hour": next_run_hour,
                }
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
