@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 Hajimi King - 一键启动
echo ========================================
echo.

REM 检查是否已初始化数据库
if not exist "data\hajimi_king.db" (
    echo ⚠️  数据库未初始化，正在初始化...
    python init_db.py
    if not exist "data\hajimi_king.db" (
        echo.
        echo ❌ 数据库初始化失败，请检查错误信息
        pause
        exit /b
    )
    echo.
    echo ✅ 数据库初始化成功
    echo.
)

REM 检查是否配置了访问密钥
findstr /C:"WEB_ACCESS_KEY=" .env >nul
if errorlevel 1 (
    echo ⚠️  未检测到 WEB_ACCESS_KEY，请在 .env 文件中配置
    echo.
    echo 示例：
    echo WEB_ACCESS_KEY=your_secret_key_here
    echo.
    pause
    exit /b
)

echo ✅ 配置检查通过
echo.
echo 📦 正在启动服务...
echo.

REM 启动挖掘程序（后台）
echo 🔍 启动挖掘程序...
start "Hajimi King - Miner" cmd /k "python -m app.hajimi_king_db"

REM 等待2秒
timeout /t 2 /nobreak >nul

REM 启动 Web Dashboard（后台）
echo 🌐 启动 Web Dashboard...
start "Hajimi King - Web" cmd /k "python start_web.py"

REM 等待3秒
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo ✅ 启动完成！
echo ========================================
echo.
echo 📡 Web Dashboard: http://localhost:8000/login
echo 📊 API 文档: http://localhost:8000/docs
echo.
echo 💡 提示：
echo    - 使用 .env 中的 WEB_ACCESS_KEY 登录
echo    - 关闭窗口可停止相应服务
echo.
pause
