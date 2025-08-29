#!/bin/bash

# --- 配置项 ---
# 项目根目录
PROJECT_ROOT="/opt/hajimi-king"
# 虚拟环境路径
VENV_PATH="${PROJECT_ROOT}/venv"
# 应用程序启动命令
APP_COMMAND="python -m app.hajimi_king" # 注意：这个变量在nohup启动中直接引用了，没有实际使用APP_COMMAND
# nohup 输出日志文件
LOG_FILE="${PROJECT_ROOT}/nohup.out"
# 进程文件，用于存储PID，确保精确管理
PID_FILE="${PROJECT_ROOT}/hajimi_king.pid"

# --- 函数定义 ---

# 检查应用程序是否正在运行
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "true"
        else
            # PID文件存在但对应的进程已不存在，说明PID文件是旧的，清理它
            echo "旧的PID文件 ${PID_FILE} 已检测到，但进程 ${PID} 未运行。正在清理..."
            rm -f "$PID_FILE"
            echo "false"
        fi
    else
        echo "false"
    fi
}


# 启动应用程序
start_app() {
    echo "正在启动 Hajimi King 应用..."
    
    # 确保停留在 PROJECT_ROOT 目录
    cd "${PROJECT_ROOT}" || (echo "错误：无法进入项目目录 ${PROJECT_ROOT}" && exit 1)

    # 检查虚拟环境中的Python解释器是否存在
    if [ ! -f "${VENV_PATH}/bin/python" ]; then
        echo "错误：虚拟环境中的Python解释器未找到！请检查路径：${VENV_PATH}/bin/python"
        echo "请确保虚拟环境已创建并正确激活过一次。"
        exit 1
    fi

    echo "日志输出到：${LOG_FILE}"
    # 运行命令，将PID写入文件
    nohup "${VENV_PATH}/bin/python" -m app.hajimi_king > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}" # 将后台进程的PID写入文件

    sleep 2 # 稍等片刻，确保进程已启动
    if [ "$(is_running)" = "true" ]; then
        echo "Hajimi King 应用已成功启动。PID: $(cat "${PID_FILE}")"
    else
        echo "错误：Hajimi King 应用启动失败。请检查日志：${LOG_FILE}"
    fi
}

# 停止应用程序
stop_app() {
    echo "正在停止 Hajimi King 应用..."
    if [ "$(is_running)" = "true" ]; then
        PID=$(cat "$PID_FILE")
        echo "发现正在运行的进程，PID: ${PID}"
        kill "$PID"
        sleep 5 # 等待进程优雅关闭
        if [ "$(is_running)" = "true" ]; then
            echo "进程 ${PID} 未能优雅停止，尝试强制终止..."
            kill -9 "$PID"
            sleep 2
            if [ "$(is_running)" = "true" ]; then
                echo "错误：进程 ${PID} 无法终止。"
            else
                echo "进程 ${PID} 已强制终止。"
                rm -f "$PID_FILE" # 删除 PID 文件
            fi
        else
            echo "进程 ${PID} 已停止。"
            rm -f "$PID_FILE" # 删除 PID 文件
        fi
    else
        echo "Hajimi King 应用未运行。"
        # 如果 PID 文件存在但进程已死，前面 is_running 已经清理了
    fi
}

# --- 主逻辑 ---

# 如果没有提供参数，则默认执行 'restart'
if [ -z "$1" ]; then
    OPERATION="restart"
else
    OPERATION="$1"
fi

case "$OPERATION" in
    start)
        if [ "$(is_running)" = "true" ]; then
            echo "Hajimi King 应用已经在运行中。PID: $(cat "${PID_FILE}")"
            echo "如果要重启，请使用 'restart' 命令或直接运行脚本。"
        else
            start_app
        fi
        ;;
    stop)
        stop_app
        ;;
    restart)
        stop_app
        start_app
        ;;
    status)
        if [ "$(is_running)" = "true" ]; then
            echo "Hajimi King 应用正在运行中。PID: $(cat "${PID_FILE}")"
        else
            echo "Hajimi King 应用未运行或 PID 文件不存在。"
        fi
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "日志文件 ${LOG_FILE} 不存在。"
        fi
        ;;
    *)
        echo "用法: $0 [start|stop|restart|status|logs]"
        echo "      不带参数运行时，默认执行 'restart'（如果已运行）或 'start'（如果未运行）。"
        exit 1
        ;;
esac

exit 0
