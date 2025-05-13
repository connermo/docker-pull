# 构建前端
FROM node:18-alpine as frontend-builder

WORKDIR /app

# 复制前端文件
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# 构建后端
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# 复制后端文件
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建下载目录
RUN mkdir -p /app/downloads

# 复制前端构建文件到后端静态文件目录
COPY --from=frontend-builder /app/build /app/backend/static

# 复制后端代码
COPY backend/ /app/backend/

# 设置工作目录
WORKDIR /app/backend

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
# 可在运行容器时覆盖以下环境变量
ENV DOCKER_REGISTRY_MIRROR=""
ENV DOCKER_HTTP_PROXY=""
ENV DOCKER_HTTPS_PROXY=""

# 启动命令
CMD ["python", "main.py"] 