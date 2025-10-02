#!/bin/bash

echo "========================================"
echo "🚀 Hajimi King - 一键启动"
echo "========================================"
echo ""

# 检查是否已初始化数据库
if [ ! -f "data/hajimi_king.db" ]; then
    echo "⚠️  数据库未初始化，正在初始化..."
    python init_db.py

    if [ ! -f "data/hajimi_king.db" ]; then
        echo ""
        echo "❌ 数据库初始化失败，请检查错误信息"
        exit 1
    fi

    echo ""
    echo "✅ 数据库初始化成功"
    echo ""
fi

# 检查是否配置了访问密钥
if ! grep -q "WEB_ACCESS_KEY=" .env; then
    echo "⚠️  未检测到 WEB_ACCESS_KEY，请在 .env 文件中配置"
    echo ""
    echo "示例："
    echo "WEB_ACCESS_KEY=your_secret_key_here"
    echo ""
    exit 1
fi

echo "✅ 配置检查通过"
echo ""
echo "📦 正在启动服务..."
echo ""

# 启动挖掘程序（后台）
echo "🔍 启动挖掘程序..."
nohup python -m app.hajimi_king_db > logs/miner.log 2>&1 &
MINER_PID=$!
echo "   PID: $MINER_PID"

# 等待2秒
sleep 2

# 启动 Web Dashboard（后台）
echo "🌐 启动 Web Dashboard..."
nohup python start_web.py > logs/web.log 2>&1 &
WEB_PID=$!
echo "   PID: $WEB_PID"

# 等待3秒
sleep 3

# 保存 PID 到文件
mkdir -p data
echo $MINER_PID > data/miner.pid
echo $WEB_PID > data/web.pid

echo ""
echo "========================================"
echo "✅ 启动完成！"
echo "========================================"
echo ""
echo "📡 Web Dashboard: http://localhost:8000/login"
echo "📊 API 文档: http://localhost:8000/docs"
echo ""
echo "📝 日志文件："
echo "   - 挖掘程序: logs/miner.log"
echo "   - Web 服务: logs/web.log"
echo ""
echo "⏹️  停止服务："
echo "   ./stop_all.sh"
echo ""
echo "💡 提示："
echo "   - 使用 .env 中的 WEB_ACCESS_KEY 登录"
echo "   - 查看日志: tail -f logs/miner.log"
echo ""
