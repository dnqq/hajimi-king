# Hajimi King - 更新日志

## [0.0.2-beta] - 2025-01-03

### ✨ 新增功能

#### 1. 数据库支持
- **SQLite 数据库**：替代文本文件存储
- **WAL 模式**：读写并发，性能优化
- **密钥加密**：使用 Fernet 加密存储所有密钥
- **SHA256 去重**：通过哈希值防止重复密钥

#### 2. Web Dashboard
- **仪表盘**：实时统计、图表展示、最近密钥
- **密钥管理**：列表、筛选、搜索、详情、批量删除
- **统计分析**：供应商对比、趋势分析、Top 仓库
- **响应式设计**：基于 Vue 3 + Element Plus

#### 3. 身份验证
- **简单密钥登录**：通过 `.env` 配置访问密钥
- **令牌存储**：浏览器 localStorage 持久化
- **API 保护**：所有 API 需要 Bearer Token

#### 4. 导出功能
- **CSV 导出**：支持筛选（供应商、状态）
- **JSON 导出**：完整数据结构

#### 5. 手动同步
- **一键同步**：Gemini Balancer / GPT Load
- **批量处理**：一次同步最多 100 个密钥
- **同步日志**：记录每次同步的成功/失败状态

#### 6. 通知系统
- **Webhook 通知**：发现有效密钥时通知
- **每日报告**：统计数据推送
- **可配置**：通过 `.env` 启用/禁用

#### 7. 代码优化
- **删除废弃代码**：移除 `extract_keys_from_content()`, `validate_gemini_key()`
- **异常处理改进**：空 `except` 改为记录日志
- **错误重试**：主循环异常后等待 60 秒
- **Dockerfile 优化**：依赖层缓存优化
- **Windows 兼容**：DATA_PATH 使用 `os.path.join`

### 📦 新增文件

**数据库相关**：
- `web/database.py` - SQLAlchemy 连接
- `web/models.py` - 6 个数据库表模型
- `web/schemas.py` - Pydantic API 模型
- `utils/crypto.py` - 密钥加密工具
- `utils/db_manager.py` - 数据库操作管理器
- `init_db.py` - 数据库初始化脚本

**Web 应用**：
- `web/main.py` - FastAPI 主应用
- `web/auth.py` - 身份验证模块
- `web/api/keys.py` - 密钥管理 API
- `web/api/stats.py` - 统计分析 API
- `web/api/scan.py` - 扫描管理 API
- `web/api/sync.py` - 同步管理 API
- `web/api/export.py` - 导出功能 API
- `web/api/notify.py` - 通知功能 API

**前端页面**：
- `web/templates/login.html` - 登录页面
- `web/templates/index.html` - 仪表盘
- `web/templates/keys.html` - 密钥管理
- `web/templates/stats.html` - 统计分析

**挖掘程序**：
- `app/hajimi_king_db.py` - 数据库版本挖掘程序

**工具脚本**：
- `start_web.py` - Web Dashboard 启动脚本
- `start_all.bat` - Windows 一键启动脚本
- `requirements-web.txt` - Web 依赖清单

**文档**：
- `README_WEB.md` - Web Dashboard 使用指南
- `FEATURES.md` - 新功能详细说明
- `CHANGELOG.md` - 更新日志

### 🔧 改进

- **pyproject.toml**：完善元数据（作者、许可证、分类）
- **env.example**：新增 Web Dashboard 配置项
- **README.md**：更新 Docker 部署说明（需要源码构建）
- **first_deploy.sh**：修正源码路径错误
- **config.py**：删除模块级别冗余日志

### 🗄️ 数据库表结构

1. **api_keys** - 密钥表（加密存储）
2. **scanned_files** - 已扫描文件（去重）
3. **scan_tasks** - 扫描任务历史
4. **sync_logs** - 同步日志
5. **system_config** - 系统配置
6. **daily_stats** - 每日统计

### 🔒 安全改进

- ✅ 密钥 Fernet 加密存储
- ✅ SHA256 哈希去重
- ✅ 访问密钥身份验证
- ✅ 环境变量隔离敏感配置
- ✅ SQL 注入防护（SQLAlchemy ORM）

### 🚀 性能优化

- ✅ SQLite WAL 模式（读写并发）
- ✅ 数据库索引优化
- ✅ Dockerfile 层缓存优化
- ✅ 分页查询（避免一次性加载大量数据）

---

## [0.0.1-beta] - 2024-12-XX

### ✨ 初始版本

- GitHub API 密钥挖掘
- 多供应商支持（Gemini、OpenAI、OpenRouter、Cerebras）
- 自动查询生成
- 密钥验证
- 文本文件存储
- 外部同步（Gemini Balancer、GPT Load）
- AI 分析未知密钥
- 增量扫描
- 代理支持

---

## 📊 版本对比

| 功能 | v0.0.1 | v0.0.2 |
|------|--------|--------|
| 数据存储 | 文本文件 | SQLite 数据库 |
| 密钥加密 | ❌ | ✅ Fernet |
| Web Dashboard | ❌ | ✅ |
| 身份验证 | ❌ | ✅ |
| 导出功能 | ❌ | ✅ CSV/JSON |
| 手动同步 | ❌ | ✅ |
| 通知功能 | ❌ | ✅ Webhook |
| 图表展示 | ❌ | ✅ ECharts |
| API 文档 | ❌ | ✅ FastAPI Swagger |
| 读写并发 | ❌ | ✅ WAL 模式 |

---

## 🔄 迁移指南

### 从 v0.0.1 迁移到 v0.0.2

**选项 1：重新开始（推荐）**
```bash
# 1. 初始化数据库
python init_db.py

# 2. 配置 .env（添加 ENCRYPTION_KEY 和 WEB_ACCESS_KEY）
# 3. 使用新的挖掘程序
python -m app.hajimi_king_db

# 4. 启动 Web Dashboard
python start_web.py
```

**选项 2：并行运行**
```bash
# 继续使用旧版挖掘程序
python -m app.hajimi_king  # 写入文本文件

# 同时运行新版（写入数据库）
python -m app.hajimi_king_db
```

**选项 3：只使用 Web Dashboard 查看**
```bash
# 手动将文本文件密钥导入数据库（需自行编写脚本）
# 然后启动 Web Dashboard 查看
```

---

## 🐛 已知问题

1. **实时日志流**：尚未实现（WebSocket）
2. **多用户支持**：当前只支持单个访问密钥
3. **密钥重新验证**：Web 界面尚未实现
4. **数据库备份**：需要手动备份 `data/hajimi_king.db`

---

## 🔮 未来计划

- [ ] WebSocket 实时日志流
- [ ] JWT 多用户支持
- [ ] 密钥重新验证功能
- [ ] 数据库自动备份
- [ ] Docker Compose 一键部署
- [ ] 更多图表（文件类型分布、语言分布）
- [ ] 邮件通知（除 Webhook 外）
- [ ] 定时任务（每日报告、自动清理）

---

**📅 更新频率**：根据需求不定期更新

**🐛 问题反馈**：https://github.com/dnqq/hajimi-king/issues
