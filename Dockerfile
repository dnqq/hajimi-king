FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DATA_PATH=/app/data
ENV TZ=Asia/Shanghai

# 安装系统依赖和时区数据
RUN apt-get update && apt-get install -y \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用 Docker 缓存层）
COPY pyproject.toml ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 复制项目代码（放在依赖安装之后）
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8787

# 启动命令（默认启动挖掘程序，可通过 docker-compose 覆盖）
CMD ["python", "-m", "app.hajimi_king_db"]
