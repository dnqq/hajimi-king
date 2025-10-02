#!/bin/bash

echo "========================================"
echo "⏹️  Hajimi King - 停止服务"
echo "========================================"
echo ""

# 读取 PID 并停止进程
if [ -f "data/miner.pid" ]; then
    MINER_PID=$(cat data/miner.pid)
    if ps -p $MINER_PID > /dev/null 2>&1; then
        echo "🛑 停止挖掘程序 (PID: $MINER_PID)..."
        kill $MINER_PID
        echo "   ✅ 已停止"
    else
        echo "⚠️  挖掘程序未运行"
    fi
    rm -f data/miner.pid
else
    echo "⚠️  未找到挖掘程序 PID 文件"
fi

echo ""

if [ -f "data/web.pid" ]; then
    WEB_PID=$(cat data/web.pid)
    if ps -p $WEB_PID > /dev/null 2>&1; then
        echo "🛑 停止 Web Dashboard (PID: $WEB_PID)..."
        kill $WEB_PID
        echo "   ✅ 已停止"
    else
        echo "⚠️  Web Dashboard 未运行"
    fi
    rm -f data/web.pid
else
    echo "⚠️  未找到 Web Dashboard PID 文件"
fi

echo ""
echo "✅ 所有服务已停止"
echo ""
