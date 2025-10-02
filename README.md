# 🎪 Hajimi King

**人人都是哈基米大王** 👑

从 GitHub 自动挖掘并验证多平台 AI API 密钥的智能工具。

[![GitHub](https://img.shields.io/badge/GitHub-dnqq%2Fhajimi--king-blue)](https://github.com/dnqq/hajimi-king)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

> ⚠️ **项目状态：** Beta 阶段 - 功能、结构、接口可能随时变化，请自行承担风险

---

## ✨ 核心特性

### 🎯 多平台支持
- **智能密钥提取** - 支持 Gemini、OpenAI、OpenRouter、Cerebras 等多个 AI 平台
- **可扩展架构** - 基于配置的供应商系统，轻松添加新平台
- **自动查询生成** - 根据供应商配置自动生成 GitHub 搜索查询

### 🔍 高效搜索
- **GitHub 代码搜索** - 基于自定义查询表达式搜索 API 密钥
- **智能过滤** - 自动过滤文档、示例、测试文件
- **增量扫描** - 支持断点续传，避免重复扫描
- **代理支持** - 多代理轮换，提高访问稳定性

### 🔐 密钥管理
- **自动验证** - 实时验证密钥有效性
- **智能分类** - 区分有效密钥、限流密钥、无效密钥
- **外部同步** - 支持同步到 [Gemini-Balancer](https://github.com/snailyp/gemini-balance) 和 [GPT-Load](https://github.com/tbphp/gpt-load)
- **AI 分析** - 使用 AI 分析未知格式的密钥配置

---

## 📋 目录

- [快速开始](#-快速开始)
- [部署方式](#-部署方式)
  - [本地部署](#本地部署)
  - [Docker 部署](#docker-部署)
- [配置说明](#-配置说明)
  - [必填配置](#必填配置)
  - [供应商配置](#供应商配置)
  - [查询配置](#查询配置)
- [高级功能](#-高级功能)
  - [自动查询生成](#自动查询生成)
  - [外部同步](#外部同步)
  - [AI 分析](#ai-分析)
- [开发指南](#-开发指南)

---

## 🚀 快速开始

### 前置要求

- Python 3.11+（本地部署）
- Docker + Docker Compose（容器部署，可选）
- GitHub Personal Access Token（[创建地址](https://github.com/settings/tokens)）

### 一键启动

**Windows:**
```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 配置环境变量
copy env.example .env
# 编辑 .env 文件

# 3. 初始化数据库
python init_db.py

# 4. 启动服务
start_all.bat
```

**Linux:**
```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 配置环境变量
cp env.example .env
# 编辑 .env 文件

# 3. 赋予执行权限
chmod +x start_all.sh stop_all.sh

# 4. 启动服务
./start_all.sh
```

**Docker:**
```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 配置环境变量
cp env.example .env
# 编辑 .env 文件

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

---

## 📦 部署方式

### Windows 部署

```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
copy env.example .env
# 编辑 .env，配置以下必填项：
# - GITHUB_TOKENS: GitHub 访问令牌
# - WEB_ACCESS_KEY: Web 访问密钥
# - ENCRYPTION_KEY: 数据加密密钥（可用 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 生成）

# 4. 初始化数据库
python init_db.py

# 5. 启动服务
start_all.bat

# 6. 访问服务
# Web Dashboard: http://localhost:8000/login
# API 文档: http://localhost:8000/docs
```

**停止服务：**
```bash
stop_all.bat
```

---

### Linux 部署

```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
cp env.example .env
# 编辑 .env，配置必填项（同 Windows）

# 4. 赋予执行权限
chmod +x start_all.sh stop_all.sh

# 5. 启动服务
./start_all.sh

# 6. 查看日志
tail -f logs/miner.log
tail -f logs/web.log
```

**停止服务：**
```bash
./stop_all.sh
```

**查看进程状态：**
```bash
# 检查挖掘程序
ps aux | grep hajimi_king_db

# 检查 Web 服务
ps aux | grep start_web
```

---

### Docker 部署

Docker 部署提供了**两个独立容器**：
- **miner**: 挖掘程序，负责扫描和验证密钥
- **web**: Web Dashboard，提供可视化管理界面

#### 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/dnqq/hajimi-king.git
cd hajimi-king

# 2. 配置环境变量
cp env.example .env
# 编辑 .env，配置必填项

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问服务
# Web Dashboard: http://localhost:8000/login
```

#### Docker Compose 配置说明

项目的 `docker-compose.yml` 已配置好以下功能：

- **双服务架构**: miner（挖掘） + web（展示）
- **数据持久化**: 自动挂载 `./data` 和 `./logs` 目录
- **自动重启**: 服务异常自动重启
- **日志轮转**: 单文件最大 10MB，保留 3 个历史文件
- **网络隔离**: 使用独立网络 `hajimi-network`

#### 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看所有日志
docker-compose logs -f

# 查看挖掘程序日志
docker-compose logs -f miner

# 查看 Web 服务日志
docker-compose logs -f web

# 重新构建镜像
docker-compose build --no-cache

# 查看服务状态
docker-compose ps
```

#### 手动 Docker 命令

如果不使用 docker-compose，也可以手动运行：

```bash
# 1. 构建镜像
docker build -t hajimi-king:latest .

# 2. 启动挖掘程序
docker run -d \
  --name hajimi-king-miner \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  hajimi-king:latest \
  python -m app.hajimi_king_db

# 3. 启动 Web Dashboard
docker run -d \
  --name hajimi-king-web \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -p 8000:8000 \
  hajimi-king:latest \
  python start_web.py
```

---

## ⚙️ 配置说明

### .env 核心配置

**.env 文件只需要配置 3 个核心参数：**

| 变量名 | 说明 | 如何获取 |
|--------|------|---------|
| `ENCRYPTION_KEY` | 数据加密密钥（Fernet 格式） | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `WEB_ACCESS_KEY` | Web Dashboard 访问密钥 | 自定义密码，用于登录 Web 界面 |
| `DATA_PATH` | 数据存储路径 | 默认：`data`，Docker: `/app/data` |

**.env 示例：**
```bash
ENCRYPTION_KEY=
WEB_ACCESS_KEY=your_secret_key_here
DATA_PATH=data
```

### Web 界面配置

**所有业务配置都在 Web 界面管理（📊 仪表盘、🔑 密钥管理、📈 统计分析、⚙️ 系统配置）：**

1. **启动服务后访问：** http://localhost:8000/login
2. **使用 `WEB_ACCESS_KEY` 登录**
3. **在"⚙️ 系统配置"页面添加：**
   - **GitHub Tokens** - 用于搜索 GitHub 代码
   - **AI 供应商** - 默认已包含 Gemini 和 OpenAI，可添加更多
   - **同步配置** - Gemini Balancer、GPT Load 同步设置
   - **搜索配置** - 自定义搜索查询（可选）
   - **AI 分析配置** - 用于分析未知密钥格式（可选）

**配置特点：**
- ✅ 现代化 Web 界面，直观易用
- ✅ 所有配置保存到数据库，重启自动加载
- ✅ 支持在线修改，无需编辑配置文件
- ✅ 实时统计图表，数据可视化

---

### 默认供应商

**数据库初始化时会自动添加两个默认供应商：**

#### 1. Gemini
```json
{
  "name": "gemini",
  "type": "gemini",
  "check_model": "gemini-2.0-flash-exp",
  "api_endpoint": "generativelanguage.googleapis.com",
  "key_patterns": ["AIzaSy[A-Za-z0-9\\-_]{33}"],
  "skip_ai_analysis": true
}
```

#### 2. OpenAI
```json
{
  "name": "openai",
  "type": "openai_style",
  "check_model": "gpt-3.5-turbo",
  "api_base_url": "https://api.openai.com/v1",
  "key_patterns": ["sk-[A-Za-z0-9\\-_]{20,100}"],
  "skip_ai_analysis": false
}
```

### 添加更多供应商

在 Web 界面的**配置页面**可以添加更多 AI 平台：

**支持的供应商类型：**
- `gemini` - Google Gemini
- `openai_style` - OpenAI 兼容 API（OpenAI、OpenRouter、Cerebras 等）

**配置字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 供应商名称（唯一标识） |
| `type` | ✅ | 供应商类型（`gemini` 或 `openai_style`） |
| `check_model` | ✅ | 验证密钥时使用的模型 |
| `api_endpoint` | Gemini 必填 | Gemini API 端点 |
| `api_base_url` | OpenAI 必填 | API 基础 URL |
| `key_patterns` | ✅ | 密钥正则表达式列表 |
| `gpt_load_group_name` | ⭕ | GPT Load 同步组名 |
| `skip_ai_analysis` | ⭕ | 是否跳过 AI 分析（默认 false） |

---

### 查询配置

#### 自动查询生成 ✨

**系统会自动根据供应商配置生成搜索查询**，无需手动维护 `data/queries.txt`！

**工作原理：**
1. 从 `AI_PROVIDERS_CONFIG` 提取密钥前缀（如 `AIzaSy`、`sk-`）
2. 自动生成精准查询（如 `"AIzaSy" in:file`）
3. 添加通用文件查询（如 `filename:.env`）

**示例输出：**
```
🔍 Detected 4 unique key prefixes from 4 providers
   - AIzaSy (gemini)
   - sk- (openai)
   - sk-or-v1- (openrouter)
   - csk- (cerebras)
✅ Generated 4 prefix-based queries
✅ Added 6 common file queries
🎯 Total auto-generated queries: 10
```

**生成的查询：**
- `"AIzaSy" in:file`
- `"sk-" in:file`
- `"csk-" in:file`
- `"sk-or-v1-" in:file`
- `filename:.env`
- `filename:.env.example`
- `filename:config.json`
- `filename:credentials.json`
- `filename:secrets.json`
- `path:config/ extension:json`

#### 手动查询（可选）

如需高级搜索，可在 `data/queries.txt` 中添加自定义查询：

```bash
# data/queries.txt

# 自动生成的查询已覆盖基础场景
# 此文件用于添加高级查询

# 示例：只搜索最近创建的文件
"AIzaSy" in:file created:>2024-01-01

# 示例：针对特定编程语言
"sk-" in:file language:python

# 示例：排除测试文件
"csk-" in:file -path:test/ -path:example/
```

> 📖 **搜索语法：** [GitHub Code Search Syntax](https://docs.github.com/en/search-github/searching-on-github/searching-code)


---

## 🎯 高级功能

### 自动查询生成

**零配置搜索** - 系统根据供应商配置自动生成 GitHub 搜索查询。

**优势：**
- ✅ 新增供应商只需修改 `.env` 中的 `AI_PROVIDERS_CONFIG`
- ✅ 自动优化查询，减少重复搜索
- ✅ 支持手动补充高级查询

**工作流程：**
```
1. 从 AI_PROVIDERS_CONFIG 提取密钥前缀
   ↓
2. 生成精准前缀查询（如 "AIzaSy" in:file）
   ↓
3. 添加通用文件查询（如 filename:.env）
   ↓
4. 合并手动查询（如果有）
   ↓
5. 开始搜索 GitHub
```

**示例：添加 Anthropic 供应商**

1. 访问 Web 配置页面
2. 在"AI 供应商配置"中点击"添加供应商"
3. 填写配置：
   ```json
   {
     "name": "anthropic",
     "type": "openai_style",
     "check_model": "claude-3-haiku-20240307",
     "api_base_url": "https://api.anthropic.com/v1",
     "key_patterns": ["sk-ant-[A-Za-z0-9\\-_]{20,100}"],
     "gpt_load_group_name": "anthropic_group"
   }
   ```
4. 保存配置
5. 重启挖掘程序，自动生成新查询！
   ```
   输出: ✨ "sk-ant-" in:file
   ```

---

### 外部同步

支持将发现的密钥同步到外部负载均衡服务：

#### Gemini Balancer

```bash
GEMINI_BALANCER_SYNC_ENABLED=true
GEMINI_BALANCER_URL=http://your-balancer.com
GEMINI_BALANCER_AUTH=your_password
```

#### GPT Load Balancer

```bash
GPT_LOAD_SYNC_ENABLED=true
GPT_LOAD_URL=http://your-gpt-load.com
GPT_LOAD_AUTH=your_password
```

**特性：**
- 异步同步，不阻塞主流程
- 按供应商分组同步（通过 `gpt_load_group_name`）
- 自动重试失败的同步请求

---

### AI 分析

当发现未知格式的 API 密钥时，使用 AI 分析文件内容提取配置信息。

#### 启用 AI 分析

```bash
AI_ANALYSIS_ENABLED=true
AI_ANALYSIS_URL=https://your-api-gateway.com/v1
AI_ANALYSIS_MODEL=gpt-4o-mini
AI_ANALYSIS_API_KEY=sk-your-api-key
```

#### 工作原理

1. 系统尝试用预设供应商验证密钥
2. 如果验证失败，且未配置 `skip_ai_analysis: true`
3. 使用 AI 分析文件内容，提取：
   - API 基础 URL（如 `https://api.example.com/v1`）
   - 使用的模型名称
   - 服务类型
4. 使用提取的信息验证密钥
5. 保存到 `data/ai_valid_keys_*.txt`

---

## 🛠️ 开发指南

### 项目结构

```
hajimi-king/
├── app/
│   ├── hajimi_king_db.py           # 主程序入口（数据库版）
│   └── providers/                  # 供应商模块
│       ├── config_based_factory.py # 供应商工厂
│       ├── config_key_extractor.py # 密钥提取器
│       └── key_extractor.py        # 密钥提取基类
├── web/                            # Web Dashboard
│   ├── main.py                     # FastAPI 主程序
│   ├── api/                        # API 路由
│   ├── templates/                  # 前端页面
│   └── models.py                   # 数据库模型
├── common/
│   ├── config.py                   # 配置管理
│   └── Logger.py                   # 日志工具
├── utils/
│   ├── github_client.py            # GitHub API 客户端
│   ├── file_manager.py             # 查询文件加载器
│   ├── sync_utils.py               # 同步工具
│   ├── ai_analyzer.py              # AI 分析器
│   ├── query_generator.py          # 查询生成器
│   ├── config_loader.py            # 数据库配置加载器
│   └── crypto.py                   # 加密工具
├── data/                           # 数据目录
│   ├── hajimi_king.db              # SQLite 数据库
│   └── queries.txt                 # 查询配置（可选）
├── logs/                           # 日志目录
├── env.example                     # 配置示例
├── init_db.py                      # 数据库初始化
├── start_web.py                    # Web 服务启动脚本
├── start_all.bat                   # Windows 启动脚本
├── stop_all.bat                    # Windows 停止脚本
├── start_all.sh                    # Linux 启动脚本
├── stop_all.sh                     # Linux 停止脚本
├── Dockerfile                      # Docker 镜像
└── docker-compose.yml              # Docker Compose
```

### 添加新供应商

**在 Web 界面添加（推荐）：**

1. 访问配置页面
2. 点击"添加供应商"
3. 填写配置并保存
4. 重启挖掘程序

**自定义供应商类（高级）：**

```python
# app/providers/config_based_factory.py

class YourCustomProvider(ConfigBasedAIProvider):
    """自定义供应商"""

    def validate_key(self, api_key: str) -> Union[bool, str]:
        """验证密钥逻辑"""
        # 实现你的验证逻辑
        pass

    def extract_keys_from_content(self, content: str) -> List[str]:
        """提取密钥逻辑"""
        # 实现你的提取逻辑
        pass

# 注册供应商类型
ConfigBasedAIProviderFactory.register_provider_type(
    'your_custom_type',
    YourCustomProvider
)
```

---

## 📊 数据存储

### 数据库结构

项目使用 **SQLite** 数据库存储所有数据：

**主要数据表：**
- `api_keys` - API 密钥记录（加密存储）
- `github_files` - GitHub 文件元数据
- `providers` - AI 供应商配置
- `github_tokens` - GitHub Token 配置
- `system_config` - 系统配置
- `sync_config` - 同步配置
- `ai_analysis_config` - AI 分析配置

**数据库位置：**
```
data/
└── hajimi_king.db              # SQLite 数据库文件
```

### 访问数据

**方式 1：Web Dashboard**
- 访问 http://localhost:8000
- 查看统计数据、密钥列表、配置管理

**方式 2：API 接口**
```bash
# 获取统计数据
curl -H "Authorization: Bearer your_access_key" \
  http://localhost:8000/api/stats/summary

# 获取密钥列表
curl -H "Authorization: Bearer your_access_key" \
  http://localhost:8000/api/keys?status=valid
```

**方式 3：直接查询数据库**
```bash
sqlite3 data/hajimi_king.db "SELECT * FROM api_keys WHERE status='valid' LIMIT 10"
```

---

## 🔒 安全建议

- ✅ **最小权限原则** - GitHub Token 只需 `public_repo` 读取权限
- ✅ **定期轮换** - 定期更换 GitHub Token
- ✅ **保护配置文件** - 不要将 `.env` 提交到版本控制
- ✅ **使用代理** - 配置代理避免 IP 被封
- ✅ **定期清理** - 及时清理发现的密钥文件
- ✅ **合规使用** - 遵守 GitHub 使用条款和 API 配额限制

---

## 📝 常见问题

### Q: 查询是如何生成的？
**A:** 系统从 `AI_PROVIDERS_CONFIG` 中提取密钥前缀（如 `AIzaSy`），自动生成精准查询和通用文件查询。无需手动维护查询文件。

### Q: 如何添加新的 AI 平台？
**A:** 只需在 `.env` 的 `AI_PROVIDERS_CONFIG` 中添加配置，系统会自动生成搜索查询。

### Q: 为什么需要配置代理？
**A:** GitHub 和 AI API 对高频访问有限制，使用代理可以避免 IP 被封。推荐使用 [warp-docker](https://github.com/cmj2002/warp-docker)。

### Q: 如何查看找到的密钥？
**A:** 访问 Web Dashboard (http://localhost:8000)，或使用 API 接口查询数据库。所有密钥都加密存储在 SQLite 数据库中。

### Q: 支持哪些 AI 平台？
**A:** 默认支持 Gemini、OpenAI、OpenRouter、Cerebras。可通过配置添加任何 OpenAI 兼容的平台。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📜 许可证

MIT License

---

## 🙏 致谢

本项目 Fork 自原始项目并进行了大量优化和功能扩展。

**主要改进：**
- ✅ 数据库存储 + Web Dashboard 管理界面
- ✅ 多平台 AI 密钥支持
- ✅ 自动查询生成系统
- ✅ 基于配置的可扩展架构
- ✅ AI 智能分析未知密钥
- ✅ 外部服务同步功能
- ✅ 完善的错误处理和日志
- ✅ 多平台部署支持（Windows/Linux/Docker）

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

**🎉 享受使用 Hajimi King 的快乐时光！**
