# Hajimi King - Web Dashboard 使用指南

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Web Dashboard 依赖
pip install -r requirements-web.txt
```

### 2. 初始化数据库

```bash
# 首次运行需要初始化数据库
python init_db.py
```

**重要**：首次运行会生成 `ENCRYPTION_KEY`，请将其添加到 `.env` 文件：

```bash
# 复制日志中显示的密钥到 .env
echo "ENCRYPTION_KEY=your_generated_key_here" >> .env
```

### 3. 启动挖掘程序（数据库版本）

```bash
# 使用数据库版本的挖掘程序
python -m app.hajimi_king_db
```

### 4. 启动 Web Dashboard

```bash
# 在另一个终端启动 Web 服务
python start_web.py
```

### 5. 访问 Dashboard

打开浏览器访问：**http://localhost:8000**

---

## 📊 功能页面

### 仪表盘（首页）
- **URL**: http://localhost:8000/
- **功能**：
  - 总密钥数、有效密钥数、限流密钥数、今日新增统计
  - 供应商密钥分布饼图
  - 最近 7 天密钥发现趋势图
  - 最近发现的密钥列表

### 密钥管理
- **URL**: http://localhost:8000/keys
- **功能**：
  - 密钥列表（分页）
  - 按供应商、状态筛选
  - 搜索仓库名或密钥
  - 查看密钥详情（完整密钥）
  - 复制密钥到剪贴板
  - 删除密钥
  - 批量删除

### 统计分析
- **URL**: http://localhost:8000/stats
- **功能**：
  - 供应商对比统计
  - 时间趋势分析
  - Top 10 来源仓库
  - 详细的图表展示

---

## 🔧 API 文档

FastAPI 自动生成的 API 文档：**http://localhost:8000/docs**

### 主要 API 端点

#### 密钥管理
- `GET /api/keys/` - 获取密钥列表（分页）
- `GET /api/keys/{key_id}` - 获取密钥详情
- `PATCH /api/keys/{key_id}` - 更新密钥
- `DELETE /api/keys/{key_id}` - 删除密钥
- `POST /api/keys/batch-delete` - 批量删除密钥

#### 统计分析
- `GET /api/stats/summary` - 获取统计摘要
- `GET /api/stats/providers` - 获取供应商统计
- `GET /api/stats/daily?days=7` - 获取每日统计
- `GET /api/stats/top-repos?limit=10` - 获取 Top 仓库
- `GET /api/stats/recent-keys?limit=10` - 获取最近密钥

#### 扫描管理
- `GET /api/scan/tasks` - 获取扫描任务列表
- `GET /api/scan/stats` - 获取扫描统计
- `GET /api/scan/recent-files` - 获取最近扫描的文件

#### 同步管理
- `GET /api/sync/logs` - 获取同步日志
- `GET /api/sync/status` - 获取同步状态
- `POST /api/sync/trigger/{target}` - 手动触发同步

---

## 📁 数据库文件位置

```
data/
├── hajimi_king.db          # SQLite 数据库文件
├── hajimi_king.db-wal      # WAL 日志（自动生成）
└── hajimi_king.db-shm      # 共享内存（自动生成）
```

**备份数据库**：
```bash
# 简单复制即可
cp data/hajimi_king.db data/hajimi_king_backup_$(date +%Y%m%d).db
```

---

## 🔐 安全说明

1. **密钥加密存储**：
   - 所有密钥使用 `ENCRYPTION_KEY` 加密存储
   - **切勿泄露 `ENCRYPTION_KEY`**
   - **切勿将 `.env` 文件提交到 Git**

2. **Web 访问控制**：
   - 默认监听 `0.0.0.0:8000`（所有网卡）
   - 生产环境建议：
     - 只监听 `127.0.0.1:8000`（本地访问）
     - 或添加身份验证（JWT/OAuth）
     - 或使用 Nginx 反向代理 + Basic Auth

---

## 🐛 常见问题

### Q: 启动 Web 时报错 "No module named 'web'"
**A**: 确保在项目根目录运行：
```bash
cd D:\code\hajimi-king
python start_web.py
```

### Q: 数据库文件锁定错误
**A**: 确保只有一个程序在写入数据库。关闭挖掘程序后再启动。

### Q: 密钥解密失败
**A**: 检查 `.env` 中的 `ENCRYPTION_KEY` 是否正确。如果密钥丢失，旧数据无法解密。

### Q: 图表不显示
**A**:
1. 检查浏览器控制台是否有 JS 错误
2. 确认 CDN 资源加载成功（ECharts、Vue、Element Plus）
3. 尝试刷新页面

### Q: 分页显示不正确
**A**: 清空浏览器缓存后重试。

---

## 🔄 从文本文件迁移到数据库

如果你之前使用的是文本文件版本（`app/hajimi_king.py`），现在想切换到数据库版本：

### 方案 1：重新开始（推荐）
```bash
# 1. 初始化数据库
python init_db.py

# 2. 使用数据库版本挖掘程序
python -m app.hajimi_king_db
```

### 方案 2：继续使用文本文件版本
保持使用 `app/hajimi_king.py`，Web Dashboard 只能查看数据库中的数据。

---

## 🎨 自定义前端

前端使用纯 HTML + Vue 3 + Element Plus，无需构建：

### 修改页面
1. 编辑 `web/templates/*.html`
2. 刷新浏览器即可看到变化

### 添加新页面
1. 在 `web/templates/` 创建 HTML 文件
2. 在 `web/main.py` 添加路由：
   ```python
   @app.get("/newpage", response_class=HTMLResponse)
   async def newpage():
       return FileResponse("web/templates/newpage.html")
   ```

---

## 📈 性能优化

### 数据库优化
```sql
-- 查看数据库大小
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();

-- 清理无效密钥（可选）
DELETE FROM api_keys WHERE status = 'invalid' AND discovered_at < datetime('now', '-30 days');

-- 重建索引
REINDEX;

-- 压缩数据库
VACUUM;
```

### Web 性能
- 分页大小建议：20-50 条
- 避免一次性加载大量数据
- 使用筛选条件减少查询量

---

## 🚀 生产部署

### Docker 部署（推荐）

编辑 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  hajimi-king-miner:
    build: .
    container_name: hajimi-king-miner
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    command: python -m app.hajimi_king_db

  hajimi-king-web:
    build: .
    container_name: hajimi-king-web
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    command: python start_web.py
    depends_on:
      - hajimi-king-miner
```

启动：
```bash
docker-compose up -d
```

---

**🎉 享受使用 Hajimi King Web Dashboard！**
