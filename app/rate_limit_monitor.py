"""
实时 Rate Limit 监控器
基于每次搜索的实际消耗，动态计算下次执行间隔
"""
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from common.Logger import logger


@dataclass
class TokenStatus:
    """单个 Token 的状态"""
    token: str

    # Search API (30/min)
    search_limit: int = 30
    search_remaining: int = 30
    search_reset: Optional[datetime] = None

    # Core API (5000/hour)
    core_limit: int = 5000
    core_remaining: int = 5000
    core_reset: Optional[datetime] = None

    # 统计信息
    last_update: datetime = field(default_factory=datetime.now)
    consecutive_errors: int = 0

    def update_search_limit(self, remaining: int, reset_timestamp: int):
        """更新 Search API 限额"""
        self.search_remaining = remaining
        self.search_reset = datetime.fromtimestamp(reset_timestamp)
        self.last_update = datetime.now()
        self.consecutive_errors = 0  # 成功则重置错误计数

    def update_core_limit(self, remaining: int, reset_timestamp: int):
        """更新 Core API 限额"""
        self.core_remaining = remaining
        self.core_reset = datetime.fromtimestamp(reset_timestamp)
        self.last_update = datetime.now()

    def mark_error(self):
        """标记错误"""
        self.consecutive_errors += 1

    def is_healthy(self) -> bool:
        """检查 Token 是否健康"""
        if self.consecutive_errors >= 3:
            return False
        if self.search_remaining < 5 or self.core_remaining < 100:
            return False
        return True

    def get_health_score(self) -> float:
        """获取健康分数 (0-1)"""
        search_score = self.search_remaining / self.search_limit
        core_score = self.core_remaining / self.core_limit
        error_penalty = max(0, 1 - self.consecutive_errors * 0.2)
        return (search_score * 0.4 + core_score * 0.4 + error_penalty * 0.2)


class RateLimitMonitor:
    """实时 Rate Limit 监控器"""

    def __init__(self):
        self.tokens: Dict[str, TokenStatus] = {}
        self.last_search_stats: Dict[str, any] = {}

        # 固定配置参数（基于算法优化后的最佳实践）
        self.min_interval_minutes = 15   # 最小间隔15分钟
        self.max_interval_minutes = 120  # 最大间隔2小时
        self.target_search_reserve = 0.3 # 保留30% Search配额（用于冷却计算）
        self.target_core_reserve = 0.2   # 保留20% Core配额

    def register_token(self, token: str):
        """注册 Token"""
        if token not in self.tokens:
            masked = token[:8] + "..." if len(token) > 8 else token
            self.tokens[token] = TokenStatus(token=masked)
            logger.info(f"📝 Registered token: {masked}")

    def update_from_response(self, token: str, headers: Dict[str, str], api_type: str = "search"):
        """从响应头更新限额信息"""
        if token not in self.tokens:
            self.register_token(token)

        status = self.tokens[token]

        try:
            remaining = int(headers.get('X-RateLimit-Remaining', 0))
            limit = int(headers.get('X-RateLimit-Limit', 0))
            reset = int(headers.get('X-RateLimit-Reset', 0))

            if api_type == "search":
                status.search_limit = limit or status.search_limit
                status.update_search_limit(remaining, reset)
            else:  # core
                status.core_limit = limit or status.core_limit
                status.update_core_limit(remaining, reset)

        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Failed to parse rate limit headers: {e}")

    def mark_token_error(self, token: str):
        """标记 Token 错误"""
        if token in self.tokens:
            self.tokens[token].mark_error()

    def get_healthiest_token(self) -> Optional[str]:
        """获取最健康的 Token"""
        if not self.tokens:
            return None

        healthy_tokens = [(t, s.get_health_score()) for t, s in self.tokens.items() if s.is_healthy()]
        if not healthy_tokens:
            return None

        return max(healthy_tokens, key=lambda x: x[1])[0]

    def record_search_execution(self, queries_count: int, files_processed: int,
                               search_requests: int, core_requests: int,
                               duration_seconds: float):
        """记录一次搜索任务的执行统计"""
        self.last_search_stats = {
            'timestamp': datetime.now(),
            'queries_count': queries_count,
            'files_processed': files_processed,
            'search_requests': search_requests,
            'core_requests': core_requests,
            'duration_seconds': duration_seconds,
            'search_rps': search_requests / duration_seconds if duration_seconds > 0 else 0,
            'core_rps': core_requests / duration_seconds if duration_seconds > 0 else 0,
        }

        logger.info(f"📊 Search execution stats: {queries_count} queries, "
                   f"{search_requests} search reqs, {core_requests} core reqs, "
                   f"duration: {duration_seconds:.1f}s")

    def calculate_next_interval(self) -> int:
        """
        实时计算下次执行间隔（秒）

        核心思想：
        1. Search API (30次/分钟) 是滑动窗口，瞬时剩余次数意义不大
        2. 关键是：任务耗时 + 冷却时间 > 限流窗口
        3. 基于实际消耗量计算安全间隔
        """
        if not self.tokens:
            logger.warning("⚠️ No tokens registered, using max interval")
            return self.max_interval_minutes * 60

        # 如果没有执行历史，使用默认最小间隔
        if not self.last_search_stats:
            logger.info(f"🧮 No execution history, using default interval: {self.min_interval_minutes} min")
            return self.min_interval_minutes * 60

        # ============================================================
        # 核心算法：基于实际消耗和限流恢复速率计算安全间隔
        # ============================================================

        last_duration = self.last_search_stats.get('duration_seconds', 0)
        search_reqs = self.last_search_stats.get('search_requests', 0)
        core_reqs = self.last_search_stats.get('core_requests', 0)

        num_tokens = len([s for s in self.tokens.values() if s.is_healthy()])
        if num_tokens == 0:
            logger.warning("⚠️ No healthy tokens, using max interval")
            return self.max_interval_minutes * 60

        # 1. Search API 限流计算（关键瓶颈）
        # 每个 token: 30次/分钟 = 0.5次/秒
        search_capacity_per_second = 0.5 * num_tokens

        # 上次任务的平均请求速率
        if last_duration > 0:
            actual_search_rps = search_reqs / last_duration
        else:
            actual_search_rps = 0

        # 安全间隔 = 让滑动窗口完全清空的时间
        # 如果上次用了25次，需要等60秒让窗口清空
        # 但因为是滑动窗口，实际可以更短

        # 计算需要多久才能"还清"上次的消耗
        if actual_search_rps > search_capacity_per_second * 0.8:
            # 消耗速率接近容量 → 需要更长冷却时间
            search_cooldown = 60 * (1.0 - self.target_search_reserve)  # 默认42秒
            reason_search = "high_rate"
        else:
            # 消耗速率正常 → 短冷却
            search_cooldown = 30  # 30秒后窗口已恢复一半
            reason_search = "normal_rate"

        # 2. Core API 限流计算
        # 每个 token: 5000次/小时 = 1.39次/秒
        core_capacity_per_second = (5000 / 3600) * num_tokens

        if last_duration > 0:
            actual_core_rps = core_reqs / last_duration
        else:
            actual_core_rps = 0

        # Core API 窗口是1小时，但我们不需要等那么久
        # 只需确保下次执行时有足够配额
        if core_reqs > 0:
            # 预估下次需要的配额
            estimated_core_needed = core_reqs * 1.2  # 留20%余量
            # 计算恢复这些配额需要多久
            core_cooldown = (estimated_core_needed / core_capacity_per_second) / 60  # 分钟
            core_cooldown = min(core_cooldown, 60)  # 最多等1小时
            reason_core = f"need_{int(estimated_core_needed)}_quota"
        else:
            core_cooldown = 0
            reason_core = "no_core_usage"

        # 3. 综合决策
        # 取两者中较大的冷却时间
        required_cooldown_minutes = max(
            search_cooldown / 60,
            core_cooldown,
            self.min_interval_minutes  # 不低于最小间隔
        )

        # 4. 根据实际消耗量调整
        # 如果上次消耗很少，可以更激进
        if search_reqs < 50:
            required_cooldown_minutes *= 0.7
            reason_adjust = "low_consumption"
        # 如果上次消耗很大，更保守
        elif search_reqs > 200:
            required_cooldown_minutes *= 1.5
            reason_adjust = "high_consumption"
        else:
            reason_adjust = "normal"

        # 5. 限制在配置范围内
        interval_minutes = max(
            self.min_interval_minutes,
            min(self.max_interval_minutes, required_cooldown_minutes)
        )

        interval_seconds = int(interval_minutes * 60)

        logger.info(
            f"🧮 Calculated next interval: {interval_minutes:.1f} min\n"
            f"   Last execution: {last_duration:.1f}s, "
            f"{search_reqs} search reqs ({actual_search_rps:.2f} rps), "
            f"{core_reqs} core reqs ({actual_core_rps:.2f} rps)\n"
            f"   Tokens: {num_tokens}, Search capacity: {search_capacity_per_second:.2f} rps, "
            f"Core capacity: {core_capacity_per_second:.2f} rps\n"
            f"   Cooldown: search={search_cooldown:.1f}s ({reason_search}), "
            f"core={core_cooldown:.1f}min ({reason_core}), "
            f"adjust={reason_adjust}"
        )

        return interval_seconds

    def get_status_summary(self) -> Dict:
        """获取状态摘要"""
        if not self.tokens:
            return {
                'total_tokens': 0,
                'healthy_tokens': 0,
                'tokens': []
            }

        token_details = []
        for token, status in self.tokens.items():
            token_details.append({
                'token': status.token,
                'search_remaining': status.search_remaining,
                'search_limit': status.search_limit,
                'core_remaining': status.core_remaining,
                'core_limit': status.core_limit,
                'health_score': status.get_health_score(),
                'is_healthy': status.is_healthy(),
                'search_reset': status.search_reset.isoformat() if status.search_reset else None,
                'core_reset': status.core_reset.isoformat() if status.core_reset else None,
            })

        return {
            'total_tokens': len(self.tokens),
            'healthy_tokens': sum(1 for s in self.tokens.values() if s.is_healthy()),
            'tokens': token_details,
            'last_search': self.last_search_stats,
            'next_interval_seconds': self.calculate_next_interval(),
        }


# 全局实例
rate_limit_monitor = RateLimitMonitor()
