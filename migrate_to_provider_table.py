"""
数据迁移脚本：从 system_config JSON 迁移到 ai_providers 表
运行: python migrate_to_provider_table.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from datetime import datetime
from web.database import SessionLocal, engine, Base
from web.models import SystemConfig
from common.Logger import logger


# 直接从 models 导入（避免重复定义）
try:
    from web.models import AIProvider
except ImportError:
    # 如果导入失败，临时定义（兼容旧版本）
    class AIProvider(Base):
        """AI 供应商配置表"""
        __tablename__ = "ai_providers"
        __table_args__ = {'extend_existing': True}

        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(50), unique=True, nullable=False, index=True)
        type = Column(String(50), nullable=False)
        check_model = Column(String(100), nullable=False)
        api_endpoint = Column(String(255))
        api_base_url = Column(String(255))
        key_patterns = Column(JSON, nullable=False)
        gpt_load_group_name = Column(String(100))
        skip_ai_analysis = Column(Boolean, default=False)
        enabled = Column(Boolean, default=True, index=True)
        custom_keywords = Column(JSON, default=[])
        sort_order = Column(Integer, default=0)
        created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
        updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def migrate():
    """执行迁移"""
    logger.info("=" * 60)
    logger.info("🔄 Starting migration: system_config -> ai_providers table")
    logger.info("=" * 60)

    # 1. 创建新表
    logger.info("📋 Creating ai_providers table...")
    AIProvider.__table__.create(engine, checkfirst=True)
    logger.info("✅ Table created")

    # 2. 读取旧数据
    db = SessionLocal()
    try:
        logger.info("📖 Reading old config from system_config...")
        old_config = db.query(SystemConfig).filter(
            SystemConfig.key == "ai_providers"
        ).first()

        if not old_config:
            logger.warning("⚠️ No ai_providers config found in system_config")
            logger.info("💡 Adding default providers...")
            default_providers = [
                {
                    "name": "gemini",
                    "type": "gemini",
                    "check_model": "gemini-2.0-flash-exp",
                    "api_endpoint": "generativelanguage.googleapis.com",
                    "key_patterns": ["AIzaSy[A-Za-z0-9\\\\-_]{33}"],
                    "gpt_load_group_name": "",
                    "skip_ai_analysis": True,
                    "custom_keywords": []
                }
            ]
            providers_data = default_providers
        else:
            providers_data = old_config.value
            logger.info(f"✅ Found {len(providers_data)} providers in old config")

        # 3. 迁移数据
        logger.info("🔄 Migrating providers to new table...")
        for idx, provider_data in enumerate(providers_data):
            # 检查是否已存在
            existing = db.query(AIProvider).filter(
                AIProvider.name == provider_data.get("name")
            ).first()

            if existing:
                logger.info(f"⏩ Provider '{provider_data.get('name')}' already exists, skipping")
                continue

            # 创建新记录
            provider = AIProvider(
                name=provider_data.get("name"),
                type=provider_data.get("type"),
                check_model=provider_data.get("check_model"),
                api_endpoint=provider_data.get("api_endpoint"),
                api_base_url=provider_data.get("api_base_url"),
                key_patterns=provider_data.get("key_patterns", []),
                gpt_load_group_name=provider_data.get("gpt_load_group_name", ""),
                skip_ai_analysis=provider_data.get("skip_ai_analysis", False),
                enabled=provider_data.get("enabled", True),
                custom_keywords=provider_data.get("custom_keywords", []),
                sort_order=idx
            )
            db.add(provider)
            logger.info(f"✅ Migrated: {provider.name}")

        db.commit()
        logger.info("✅ Migration completed successfully")

        # 4. 验证
        count = db.query(AIProvider).count()
        logger.info(f"📊 Total providers in new table: {count}")

        # 5. 备份旧配置（可选）
        if old_config:
            logger.info("💾 Backing up old config...")
            backup_config = SystemConfig(
                key="ai_providers_backup",
                value=old_config.value,
                description=f"Backup before migration at {datetime.utcnow().isoformat()}"
            )
            db.merge(backup_config)
            db.commit()
            logger.info("✅ Old config backed up to 'ai_providers_backup'")

        logger.info("=" * 60)
        logger.info("🎉 Migration completed!")
        logger.info("=" * 60)
        logger.info("\n💡 Next steps:")
        logger.info("1. Restart your application")
        logger.info("2. The system will now use the new ai_providers table")
        logger.info("3. Old config in system_config is kept as backup\n")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
