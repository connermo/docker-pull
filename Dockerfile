# Build frontend
FROM node:18-alpine as frontend-builder

# 设置构建时代理参数
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

# 应用代理设置到环境变量
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV no_proxy=${no_proxy}

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Final stage
FROM python:3.11-slim

# 设置构建时代理参数
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

# 应用代理设置到环境变量
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV no_proxy=${no_proxy}

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    nginx \
    pigz \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheel
RUN python -m pip install --upgrade pip setuptools wheel

# Copy backend files
COPY backend/requirements.txt .

# Install Python dependencies with better error handling and retry
RUN pip install --no-cache-dir --default-timeout=100 --retries=3 -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/backend/downloads
RUN mkdir -p /app/backend/static

# Copy frontend build files
COPY --from=frontend-builder /app/build/* /app/backend/static/
COPY --from=frontend-builder /app/build/static /app/backend/static/static

# Copy backend code
COPY backend/ /app/backend/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set working directory
WORKDIR /app/backend

# Expose ports
EXPOSE 8000

# Set environment variables
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Create simple startup script
RUN echo '#!/bin/bash\n\
# 从 DOCKER_PROXY 自动生成所有代理环境变量\n\
if [ -n "$DOCKER_PROXY" ] && [ "$DOCKER_PROXY" != "" ]; then\n\
    echo "配置代理: $DOCKER_PROXY"\n\
    export HTTP_PROXY="$DOCKER_PROXY"\n\
    export HTTPS_PROXY="$DOCKER_PROXY"\n\
    export http_proxy="$DOCKER_PROXY"\n\
    export https_proxy="$DOCKER_PROXY"\n\
    export NO_PROXY="localhost,127.0.0.1,::1,*.local,*.internal"\n\
    export no_proxy="localhost,127.0.0.1,::1,*.local,*.internal"\n\
    echo "代理环境变量已设置:"\n\
    echo "  HTTP_PROXY=$HTTP_PROXY"\n\
    echo "  HTTPS_PROXY=$HTTPS_PROXY"\n\
    echo "  NO_PROXY=$NO_PROXY"\n\
else\n\
    echo "未设置代理，使用直连"\n\
    # 确保没有代理相关的环境变量\n\
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy\n\
fi\n\
\n\
# 启动nginx服务\n\
echo "启动nginx服务..."\n\
service nginx start\n\
\n\
# 检查Docker socket连接\n\
echo "检查Docker socket连接..."\n\
if [ -S /var/run/docker.sock ]; then\n\
    echo "Docker socket已挂载: /var/run/docker.sock"\n\
else\n\
    echo "警告: Docker socket未找到"\n\
fi\n\
\n\
# 启动Python应用，确保环境变量传递\n\
echo "启动Python应用..."\n\
exec python main.py' > /app/start.sh && \
    chmod +x /app/start.sh

# Start both nginx and backend
CMD ["/app/start.sh"] 