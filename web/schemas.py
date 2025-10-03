"""
Pydantic 模型定义（API 请求/响应）
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ============= API Key Schemas =============

class APIKeyBase(BaseModel):
    """API 密钥基础模型"""
    provider: str
    status: str
    source_repo: Optional[str] = None
    source_file_path: Optional[str] = None
    source_file_url: Optional[str] = None
    gpt_load_group_name: Optional[str] = None


class APIKeyCreate(APIKeyBase):
    """创建密钥（API 请求）"""
    key: str  # 明文密钥（用于加密）


class APIKeyResponse(APIKeyBase):
    """密钥响应（API 返回）"""
    id: int
    key_hash: str
    key_encrypted: str  # 加密后的密钥
    discovered_at: datetime
    last_validated_at: Optional[datetime]
    synced_to_balancer: bool
    synced_to_gpt_load: bool
    extra_data: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIKeyListItem(BaseModel):
    """密钥列表项（简化版）"""
    id: int
    provider: str
    status: str
    source_repo: Optional[str]
    discovered_at: datetime
    synced_to_balancer: bool
    synced_to_gpt_load: bool
    key_preview: str  # 脱敏密钥（前 8 位）

    class Config:
        from_attributes = True


class APIKeyUpdate(BaseModel):
    """更新密钥"""
    status: Optional[str] = None
    synced_to_balancer: Optional[bool] = None
    synced_to_gpt_load: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None


class BatchUpdateProviderRequest(BaseModel):
    """批量更改供应商请求"""
    key_ids: List[int]
    provider: str


# ============= Statistics Schemas =============

class StatsSummary(BaseModel):
    """统计摘要"""
    total_keys: int
    valid_keys: int
    rate_limited_keys: int
    invalid_keys: int
    pending_keys: int
    today_keys: int
    pending_balancer_sync: int
    pending_gpt_load_sync: int


class ProviderStat(BaseModel):
    """供应商统计"""
    provider: str
    total_keys: int
    valid_keys: int
    rate_limited_keys: int
    invalid_keys: int
    valid_rate: float  # 有效率百分比


class DailyStatResponse(BaseModel):
    """每日统计响应"""
    date: datetime
    provider: Optional[str]
    keys_discovered: int
    valid_keys_count: int
    rate_limited_count: int
    invalid_keys_count: int

    class Config:
        from_attributes = True


# ============= Scan Task Schemas =============

class ScanTaskResponse(BaseModel):
    """扫描任务响应"""
    id: int
    query_text: str
    status: str
    files_scanned: int
    keys_found: int
    valid_keys_count: int
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]

    class Config:
        from_attributes = True


# ============= Sync Log Schemas =============

class SyncLogResponse(BaseModel):
    """同步日志响应"""
    id: int
    key_id: int
    target_service: str
    group_name: Optional[str]
    status: str
    error_message: Optional[str]
    synced_at: datetime

    class Config:
        from_attributes = True


# ============= Pagination =============

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: List[Any]
