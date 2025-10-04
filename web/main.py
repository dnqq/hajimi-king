"""
FastAPI 主应用
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from web.api import keys, stats, scan, sync, export, notify, config, rate_limit
from web.auth import WEB_ACCESS_KEY
from common.Logger import logger

# 创建 FastAPI 应用
app = FastAPI(
    title="Hajimi King Dashboard",
    description="GitHub API Key Mining Dashboard",
    version="0.0.1-beta"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(keys.router, prefix="/api/keys", tags=["Keys"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])
app.include_router(scan.router, prefix="/api/scan", tags=["Scan"])
app.include_router(sync.router, prefix="/api/sync", tags=["Sync"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(notify.router, prefix="/api/notify", tags=["Notify"])
app.include_router(config.router, tags=["Config"])
app.include_router(rate_limit.router, prefix="/api", tags=["Rate Limit"])

# 静态文件服务
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 模板目录
templates_dir = os.path.join(os.path.dirname(__file__), "templates")


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """登录页面"""
    login_path = os.path.join(templates_dir, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return HTMLResponse("<h1>Login</h1>")


@app.post("/api/auth/login")
async def login(request: Request):
    """登录验证"""
    data = await request.json()
    access_key = data.get("access_key", "")

    # 如果未配置密钥，任何密钥都可以通过
    if not WEB_ACCESS_KEY:
        return {"success": True, "token": "dev_mode_no_auth"}

    # 验证密钥
    if access_key == WEB_ACCESS_KEY:
        return {"success": True, "token": access_key}
    else:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid access key"}
        )


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页 - 仪表盘"""
    index_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Hajimi King Dashboard</h1><p>Welcome!</p>")


@app.get("/keys", response_class=HTMLResponse)
async def keys_page():
    """密钥管理页面"""
    keys_path = os.path.join(templates_dir, "keys.html")
    if os.path.exists(keys_path):
        return FileResponse(keys_path)
    return HTMLResponse("<h1>Keys Management</h1>")


@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    """统计分析页面"""
    stats_path = os.path.join(templates_dir, "stats.html")
    if os.path.exists(stats_path):
        return FileResponse(stats_path)
    return HTMLResponse("<h1>Statistics</h1>")


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    """配置管理页面"""
    config_path = os.path.join(templates_dir, "config.html")
    if os.path.exists(config_path):
        return FileResponse(config_path)
    return HTMLResponse("<h1>Configuration</h1>")


@app.get("/providers", response_class=HTMLResponse)
async def providers_page():
    """AI供应商管理页面"""
    providers_path = os.path.join(templates_dir, "providers.html")
    if os.path.exists(providers_path):
        return FileResponse(providers_path)
    return HTMLResponse("<h1>AI Providers Management</h1>")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "hajimi-king"}


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("🚀 Hajimi King Web Dashboard starting...")
    logger.info("📡 API docs: http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("🛑 Hajimi King Web Dashboard shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
