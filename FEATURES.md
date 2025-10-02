# Hajimi King - 新功能说明

## ✨ 新增功能概览

### 1. 🔐 简单密钥身份验证
- **配置方式**：在 `.env` 文件中设置 `WEB_ACCESS_KEY`
- **登录页面**：http://localhost:8000/login
- **安全性**：
  - 访问令牌保存在浏览器 localStorage
  - API 请求通过 `Authorization: Bearer {token}` 验证
  - 未配置密钥时发出警告但允许访问（开发模式）

**配置示例**：
```bash
# .env
WEB_ACCESS_KEY=my_super_secret_key_2025
```

**登录方式**：
1. 访问 http://localhost:8000/login
2. 输入访问密钥
3. 登录成功后跳转到仪表盘

---

### 2. 📊 完整统计分析页面
- **URL**: http://localhost:8000/stats

**功能列表**：
- ✅ 供应商密钥数量对比（柱状图）
- ✅ 供应商有效率对比（百分比柱状图）
- ✅ 最近30天密钥发现趋势（折线图）
- ✅ Top 10 密钥来源仓库（横向柱状图）
- ✅ 手动同步功能（一键同步到 Balancer/GPT Load）
- ✅ 密钥导出功能（CSV/JSON）

**使用方法**：
```bash
# 访问统计页面
浏览器打开: http://localhost:8000/stats

# 手动同步
点击"立即同步"按钮，系统会：
1. 获取所有待同步密钥（最多100个）
2. 逐个同步到目标服务
3. 更新数据库同步状态
4. 显示成功/失败统计

# 导出密钥
点击"导出 CSV" 或 "导出 JSON"
浏览器会自动下载文件
```

---

### 3. 🔄 手动同步功能
- **API 端点**：
  - `POST /api/sync/trigger/balancer` - 同步到 Gemini Balancer
  - `POST /api/sync/trigger/gpt_load` - 同步到 GPT Load

**功能特性**：
- ✅ 检查同步配置是否启用
- ✅ 批量同步待处理密钥
- ✅ 记录同步日志
- ✅ 返回详细同步结果（成功数、失败数）

**API 调用示例**：
```bash
# 使用 curl 手动触发同步
curl -X POST http://localhost:8000/api/sync/trigger/balancer \
  -H "Authorization: Bearer your_access_key"

# 响应示例
{
  "success": true,
  "message": "Sync completed",
  "total": 50,
  "success_count": 48,
  "fail_count": 2
}
```

---

### 4. 📤 密钥导出功能
- **API 端点**：
  - `GET /api/export/csv` - 导出为 CSV 文件
  - `GET /api/export/json` - 导出为 JSON 文件

**支持筛选**：
- `provider` - 按供应商筛选（gemini, openai, etc.）
- `status` - 按状态筛选（valid, rate_limited, invalid）

**导出字段**（CSV）：
```csv
ID,Provider,Key,Status,Source Repo,Source File,Source URL,Discovered At,Synced to Balancer,Synced to GPT Load,GPT Load Group
1,gemini,AIzaSyXXXXXX,valid,user/repo,config.py,https://...,2025-01-03 12:00:00,Yes,Yes,gemini_group
```

**使用示例**：
```bash
# 导出所有有效的 Gemini 密钥为 CSV
curl "http://localhost:8000/api/export/csv?provider=gemini&status=valid" \
  -H "Authorization: Bearer your_access_key" \
  -o gemini_keys.csv

# 导出所有密钥为 JSON
curl "http://localhost:8000/api/export/json" \
  -H "Authorization: Bearer your_access_key" \
  -o all_keys.json
```

---

### 5. 📢 通知功能（Webhook）
- **配置方式**：在 `.env` 中设置
  ```bash
  NOTIFY_ENABLED=true
  NOTIFY_WEBHOOK_URL=https://your-webhook-url.com/notify
  ```

**通知时机**：
1. **发现有效密钥时**（需在挖掘程序中集成）
2. **每日统计报告**（可通过定时任务调用）

**Webhook 数据格式**：
```json
{
  "title": "🎉 发现有效 GEMINI 密钥",
  "message": "来自仓库: user/repo",
  "timestamp": "2025-01-03T12:00:00Z",
  "data": {
    "provider": "gemini",
    "key_preview": "AIzaSy****",
    "source_repo": "user/repo"
  }
}
```

**API 端点**：
- `GET /api/notify/config` - 获取通知配置
- `POST /api/notify/test` - 测试通知

**测试通知**：
```bash
curl -X POST http://localhost:8000/api/notify/test \
  -H "Authorization: Bearer your_access_key"
```

**集成到挖掘程序**（可选）：
```python
# 在 app/hajimi_king_db.py 的 process_item 函数中
from web.api.notify import notify_valid_key_found

# 发现有效密钥时发送通知
if validation_result and "ok" in validation_result:
    valid_keys.append(key)
    logger.info(f"✅ VALID {provider_name.upper()}: {key}")

    # 发送通知
    notify_valid_key_found(
        provider=provider_name,
        key_preview=key[:8] + "****",
        source_repo=repo_name
    )
```

**每日报告**（可选，通过 cron/定时任务）：
```python
from web.api.notify import send_daily_report
from utils.db_manager import db_manager

# 每天执行
stats = db_manager.get_stats_summary()
send_daily_report(stats)
```

---

## 🎯 完整功能列表

### 仪表盘页面 (`/`)
- [x] 总密钥数、有效密钥数、限流密钥数、今日新增统计
- [x] 供应商密钥分布饼图
- [x] 最近 7 天密钥发现趋势图
- [x] 最近发现的密钥列表（10条）

### 密钥管理页面 (`/keys`)
- [x] 密钥列表（分页：20/50/100）
- [x] 按供应商筛选
- [x] 按状态筛选
- [x] 搜索仓库名或密钥
- [x] 查看密钥详情（完整密钥、来源信息）
- [x] 一键复制密钥
- [x] 删除密钥
- [x] 批量删除

### 统计分析页面 (`/stats`)
- [x] 供应商密钥数量对比图
- [x] 供应商有效率对比图
- [x] 最近 30 天密钥发现趋势图
- [x] Top 10 密钥来源仓库
- [x] 手动同步到 Gemini Balancer
- [x] 手动同步到 GPT Load
- [x] 导出 CSV
- [x] 导出 JSON

### 身份验证
- [x] 登录页面（`/login`）
- [x] 访问密钥验证
- [x] 自动跳转未登录用户

### API 功能
- [x] 密钥管理（增删改查）
- [x] 统计分析（摘要、供应商、每日、Top仓库）
- [x] 扫描管理（任务列表、统计）
- [x] 同步管理（日志、状态、手动触发）
- [x] 导出功能（CSV、JSON）
- [x] 通知功能（Webhook、测试）

---

## 🔒 安全建议

1. **必须配置访问密钥**：
   ```bash
   # 生成强密钥
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # 添加到 .env
   WEB_ACCESS_KEY=生成的密钥
   ```

2. **保护 ENCRYPTION_KEY**：
   - 首次运行 `init_db.py` 会生成
   - **丢失后无法解密旧数据**
   - 备份到安全位置

3. **限制访问IP**（可选）：
   - 修改 `start_web.py`：
     ```python
     uvicorn.run("web.main:app", host="127.0.0.1", port=8000)  # 只允许本地访问
     ```

4. **使用 HTTPS**（生产环境）：
   - 使用 Nginx 反向代理
   - 配置 SSL 证书

---

## 📝 配置检查清单

启动前确保 `.env` 文件包含以下配置：

```bash
# 必填
GITHUB_TOKENS=ghp_your_token_here
ENCRYPTION_KEY=your_generated_encryption_key
WEB_ACCESS_KEY=your_secret_access_key

# 可选（推荐）
PROXY=http://your-proxy:port
GEMINI_BALANCER_SYNC_ENABLED=false
GPT_LOAD_SYNC_ENABLED=true
GPT_LOAD_URL=https://your-gpt-load.com
GPT_LOAD_AUTH=your_password

# 可选（通知）
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_URL=https://your-webhook-url.com/notify
```

---

## 🚀 启动流程

```bash
# 1. 安装依赖
pip install -r requirements-web.txt

# 2. 初始化数据库
python init_db.py
# ⚠️ 复制 ENCRYPTION_KEY 到 .env

# 3. 配置访问密钥
echo "WEB_ACCESS_KEY=your_secret_key" >> .env

# 4. 启动挖掘程序（数据库版本）
python -m app.hajimi_king_db

# 5. 启动 Web Dashboard（另一个终端）
python start_web.py

# 6. 访问 Dashboard
浏览器打开: http://localhost:8000/login
输入访问密钥登录
```

---

**🎉 享受使用 Hajimi King 的新功能！**
