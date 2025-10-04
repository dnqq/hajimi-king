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


class TelegramConfig(BaseModel):
    """Telegram 配置"""
    bot_token: str = ""
    chat_id: str = ""


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
        }),
        "telegram": get_config_value(db, "telegram_config", {
            "bot_token": "",
            "chat_id": ""
        })
    }


@router.get("/ai_providers")
async def get_ai_providers(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    获取 AI 供应商配置（从 ai_providers 表读取）
    """
    from web.models import AIProvider

    providers = db.query(AIProvider).filter(AIProvider.enabled == True).order_by(AIProvider.sort_order).all()
    return [provider.to_dict() for provider in providers]


@router.post("/ai_providers")
async def update_ai_providers(
    providers: List[AIProviderConfig],
    db: Session = Depends(get_db)
):
    """
    更新 AI 供应商配置（保存到 ai_providers 表）
    """
    from web.models import AIProvider

    try:
        # 删除所有现有供应商
        db.query(AIProvider).delete()

        # 添加新供应商
        for idx, provider_config in enumerate(providers):
            provider_data = provider_config.model_dump()
            provider = AIProvider(
                name=provider_data["name"],
                type=provider_data["type"],
                check_model=provider_data["check_model"],
                api_endpoint=provider_data.get("api_endpoint"),
                api_base_url=provider_data.get("api_base_url"),
                key_patterns=provider_data["key_patterns"],
                gpt_load_group_name=provider_data.get("gpt_load_group_name", ""),
                skip_ai_analysis=provider_data.get("skip_ai_analysis", False),
                enabled=True,
                custom_keywords=provider_data.get("custom_keywords", []),
                sort_order=idx
            )
            db.add(provider)

        db.commit()

        # 重新加载配置（热更新）
        from common.config import config
        config.reload_config()

        logger.info(f"✅ Updated AI providers: {len(providers)} providers (hot reloaded)")
        return {"success": True, "message": f"Updated {len(providers)} providers (hot reloaded)"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update AI providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    config_data: GithubConfig,
    db: Session = Depends(get_db)
):
    """
    更新 GitHub 配置
    """
    set_config_value(db, "github_config", config_data.model_dump(), "GitHub Tokens 和代理配置")

    # 重新加载配置（热更新）
    from common.config import config
    config.reload_config()

    logger.info(f"✅ Updated GitHub config: {len(config_data.tokens)} tokens, {len(config_data.proxy)} proxies (hot reloaded)")
    return {"success": True, "message": "GitHub config updated (hot reloaded)"}


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

    # 重新加载配置
    from common.config import config
    config.reload_config()

    logger.info(f"✅ Updated config: {config_key}")
    return {"success": True, "message": f"Config '{config_key}' updated"}


@router.post("/reload")
async def reload_config():
    """
    手动重新加载配置（热更新）
    """
    from common.config import config
    config.reload_config()

    logger.info("🔄 Configuration manually reloaded")
    return {"success": True, "message": "Configuration reloaded successfully"}


@router.get("/telegram")
async def get_telegram_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    获取 Telegram 配置
    """
    return get_config_value(db, "telegram_config", {
        "bot_token": "",
        "chat_id": ""
    })


@router.post("/telegram")
async def update_telegram_config(
    config_data: TelegramConfig,
    db: Session = Depends(get_db)
):
    """
    更新 Telegram 配置
    """
    set_config_value(db, "telegram_config", config_data.model_dump(), "Telegram 通知配置")

    # 重新加载 Telegram 通知器
    from utils.telegram_notifier import reload_telegram_notifier
    reload_telegram_notifier()

    logger.info("✅ Updated Telegram config (hot reloaded)")
    return {"success": True, "message": "Telegram config updated (hot reloaded)"}


@router.post("/telegram/test")
async def test_telegram(db: Session = Depends(get_db)):
    """
    测试 Telegram 配置
    """
    from utils.telegram_notifier import TelegramNotifier

    # 获取配置
    telegram_config = get_config_value(db, "telegram_config", {})
    bot_token = telegram_config.get('bot_token', '')
    chat_id = telegram_config.get('chat_id', '')

    if not bot_token or not chat_id:
        return {"success": False, "message": "Telegram 配置不完整"}

    # 发送测试消息
    notifier = TelegramNotifier(bot_token, chat_id)
    success = notifier.send_message(
        "🧪 <b>测试消息</b>\n\n"
        "如果你收到这条消息，说明 Telegram 配置成功！\n\n"
        "✅ 哈基米系统"
    )

    if success:
        return {"success": True, "message": "测试消息已发送"}
    else:
        return {"success": False, "message": "发送测试消息失败，请检查配置"}
