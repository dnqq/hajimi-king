"""
配置管理 API
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from web.database import get_db
from web.models import SystemConfig
from common.Logger import logger

router = APIRouter(prefix="/api/config", tags=["config"])


# ============= Pydantic Models =============

class ConfigItem(BaseModel):
    """配置项"""
    key: str
    value: Any
    description: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    value: Any


class AIProviderConfig(BaseModel):
    """AI 供应商配置"""
    name: str
    type: str
    check_model: str
    api_endpoint: Optional[str] = None
    api_base_url: Optional[str] = None
    key_patterns: List[str]
    gpt_load_group_name: Optional[str] = ""
    skip_ai_analysis: bool = False


class SyncConfig(BaseModel):
    """同步配置"""
    gemini_balancer_enabled: bool = False
    gemini_balancer_url: str = ""
    gemini_balancer_auth: str = ""

    gpt_load_enabled: bool = False
    gpt_load_url: str = ""
    gpt_load_auth: str = ""


class SearchConfig(BaseModel):
    """搜索配置"""
    date_range_days: int = 730
    file_path_blacklist: List[str] = []


class AIAnalysisConfig(BaseModel):
    """AI 分析配置"""
    enabled: bool = False
    url: str = ""
    model: str = "gpt-4o-mini"
    api_key: str = ""


class GithubConfig(BaseModel):
    """GitHub 配置"""
    tokens: List[str] = []
    proxy: List[str] = []


# ============= Helper Functions =============

def get_config_value(db: Session, key: str, default: Any = None) -> Any:
    """获取配置值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        return config.value
    return default


def set_config_value(db: Session, key: str, value: Any, description: str = "") -> SystemConfig:
    """设置配置值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config:
        config.value = value
        if description:
            config.description = description
    else:
        config = SystemConfig(
            key=key,
            value=value,
            description=description
        )
        db.add(config)

    db.commit()
    db.refresh(config)
    return config


# ============= API Endpoints =============

@router.get("/all")
async def get_all_configs(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取所有配置
    """
    return {
        "ai_providers": get_config_value(db, "ai_providers", []),
        "sync": get_config_value(db, "sync_config", {
            "gemini_balancer_enabled": False,
            "gemini_balancer_url": "",
            "gemini_balancer_auth": "",
            "gpt_load_enabled": False,
            "gpt_load_url": "",
            "gpt_load_auth": ""
        }),
        "search": get_config_value(db, "search_config", {
            "date_range_days": 730,
            "file_path_blacklist": ["readme", "docs", "doc/", ".md", "example", "sample", "tutorial"]
        }),
        "ai_analysis": get_config_value(db, "ai_analysis_config", {
            "enabled": False,
            "url": "",
            "model": "gpt-4o-mini",
            "api_key": ""
        }),
        "github": get_config_value(db, "github_config", {
            "tokens": [],
            "proxy": []
        })
    }


@router.get("/ai_providers")
async def get_ai_providers(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    获取 AI 供应商配置
    """
    return get_config_value(db, "ai_providers", [])


@router.post("/ai_providers")
async def update_ai_providers(
    providers: List[AIProviderConfig],
    db: Session = Depends(get_db)
):
    """
    更新 AI 供应商配置
    """
    providers_data = [p.model_dump() for p in providers]
    set_config_value(db, "ai_providers", providers_data, "AI 供应商配置")

    logger.info(f"✅ Updated AI providers config: {len(providers_data)} providers")
    return {"success": True, "message": f"Updated {len(providers_data)} providers"}


@router.get("/sync")
async def get_sync_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取同步配置
    """
    return get_config_value(db, "sync_config", {
        "gemini_balancer_enabled": False,
        "gemini_balancer_url": "",
        "gemini_balancer_auth": "",
        "gpt_load_enabled": False,
        "gpt_load_url": "",
        "gpt_load_auth": ""
    })


@router.post("/sync")
async def update_sync_config(
    config: SyncConfig,
    db: Session = Depends(get_db)
):
    """
    更新同步配置
    """
    set_config_value(db, "sync_config", config.model_dump(), "同步配置（Gemini Balancer / GPT Load）")

    logger.info(f"✅ Updated sync config")
    return {"success": True, "message": "Sync config updated"}


@router.get("/search")
async def get_search_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取搜索配置
    """
    return get_config_value(db, "search_config", {
        "date_range_days": 730,
        "file_path_blacklist": ["readme", "docs", "doc/", ".md", "example", "sample", "tutorial"]
    })


@router.post("/search")
async def update_search_config(
    config: SearchConfig,
    db: Session = Depends(get_db)
):
    """
    更新搜索配置
    """
    set_config_value(db, "search_config", config.model_dump(), "搜索配置（日期范围、黑名单）")

    logger.info(f"✅ Updated search config")
    return {"success": True, "message": "Search config updated"}


@router.get("/ai_analysis")
async def get_ai_analysis_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取 AI 分析配置
    """
    return get_config_value(db, "ai_analysis_config", {
        "enabled": False,
        "url": "",
        "model": "gpt-4o-mini",
        "api_key": ""
    })


@router.post("/ai_analysis")
async def update_ai_analysis_config(
    config: AIAnalysisConfig,
    db: Session = Depends(get_db)
):
    """
    更新 AI 分析配置
    """
    set_config_value(db, "ai_analysis_config", config.model_dump(), "AI 分析配置")

    logger.info(f"✅ Updated AI analysis config")
    return {"success": True, "message": "AI analysis config updated"}


@router.get("/github")
async def get_github_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取 GitHub 配置
    """
    return get_config_value(db, "github_config", {
        "tokens": [],
        "proxy": []
    })


@router.post("/github")
async def update_github_config(
    config: GithubConfig,
    db: Session = Depends(get_db)
):
    """
    更新 GitHub 配置
    """
    set_config_value(db, "github_config", config.model_dump(), "GitHub Tokens 和代理配置")

    logger.info(f"✅ Updated GitHub config: {len(config.tokens)} tokens, {len(config.proxy)} proxies")
    return {"success": True, "message": "GitHub config updated"}


@router.get("/{config_key}")
async def get_config(config_key: str, db: Session = Depends(get_db)) -> ConfigItem:
    """
    获取单个配置项
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == config_key).first()

    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    return ConfigItem(
        key=config.key,
        value=config.value,
        description=config.description
    )


@router.put("/{config_key}")
async def update_config(
    config_key: str,
    request: ConfigUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    更新单个配置项
    """
    set_config_value(db, config_key, request.value)

    logger.info(f"✅ Updated config: {config_key}")
    return {"success": True, "message": f"Config '{config_key}' updated"}
