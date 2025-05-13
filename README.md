# Docker镜像下载器

这是一个用于下载 Docker 镜像并保存为 tar 文件的 Web 应用程序，使用 React 前端和 FastAPI 后端构建。

## 功能特点

- 通过输入名称直接下载 Docker 镜像
- 实时显示下载进度
- 列出所有已下载的镜像
- 一键清空所有已下载镜像
- 支持重新下载已存在的镜像
- 使用环境变量进行灵活配置

## 技术栈

### 前端
- React 18
- TypeScript
- Tailwind CSS
- Axios

### 后端
- Python 3.11
- FastAPI
- Uvicorn
- Docker SDK

## 安装与运行

### 前提条件

- Node.js >= 16
- Python >= 3.9
- Docker

### 手动安装

1. 克隆仓库
   ```bash
   git clone https://github.com/yourusername/docker-pull.git
   cd docker-pull
   ```

2. 安装前端依赖
   ```bash
   npm install
   ```

3. 安装后端依赖
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. 创建环境变量配置文件
   ```bash
   # 在项目根目录创建前端配置
   cp env.example .env
   
   # 在后端目录创建后端配置
   cd backend
   cp ../env.example .env
   ```
   
   根据需要修改配置文件中的参数。

5. 构建前端
   ```bash
   npm run build
   ```

6. 复制前端构建文件到后端静态目录
   ```bash
   mkdir -p backend/static
   cp -r build/* backend/static/
   ```

7. 启动后端服务
   ```bash
   cd backend
   python main.py
   ```

8. 访问应用程序
   浏览器打开 http://localhost:8000

### 使用 Docker 安装

1. 构建 Docker 镜像
   ```bash
   docker build -t docker-pull .
   ```

2. 运行容器
   ```bash
   docker run -d \
     --name docker-pull \
     -p 8000:8000 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v $(pwd)/backend/downloads:/app/backend/downloads \
     docker-pull
   ```

   带网络配置的示例：
   ```bash
   docker run -d \
     --name docker-pull \
     -p 8000:8000 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v $(pwd)/backend/downloads:/app/backend/downloads \
     -e DOCKER_REGISTRY_MIRROR=https://registry.docker-cn.com \
     -e DOCKER_HTTP_PROXY=http://proxy.example.com:8080 \
     -e DOCKER_HTTPS_PROXY=http://proxy.example.com:8080 \
     docker-pull
   ```

3. 访问应用程序
   浏览器打开 http://localhost:8000

## 环境变量配置

### 前端环境变量 (.env)
```
# API 接口地址
REACT_APP_API_URL=http://localhost:8000/api
# 静态资源路径
REACT_APP_STATIC_URL=/static
# 前端开发服务器端口
PORT=3000
```

### 后端环境变量 (backend/.env)
```
# API 服务器主机地址
API_HOST=0.0.0.0
# API 服务器端口
API_PORT=8000
# 允许的跨域来源，多个来源用逗号分隔
CORS_ORIGINS=http://localhost:3000
# 下载文件存储目录，如果不指定，则使用默认路径 ./downloads
DOWNLOADS_DIR=./downloads
# Docker 镜像仓库镜像地址 (可选)
DOCKER_REGISTRY_MIRROR=https://mirror.example.com
# Docker HTTP 代理设置 (可选)
DOCKER_HTTP_PROXY=http://proxy.example.com:8080
# Docker HTTPS 代理设置 (可选)
DOCKER_HTTPS_PROXY=http://proxy.example.com:8080
```

### Docker 网络配置

本应用支持两种方式加速 Docker 镜像下载：

1. **使用镜像仓库镜像（Registry Mirror）**：
   - 设置 `DOCKER_REGISTRY_MIRROR` 环境变量指向镜像仓库地址
   - 例如：`DOCKER_REGISTRY_MIRROR=https://registry.docker-cn.com`
   - 这将在 `docker pull` 命令中自动添加 `--registry-mirror` 参数

2. **使用 HTTP/HTTPS 代理**：
   - 设置 `DOCKER_HTTP_PROXY` 和 `DOCKER_HTTPS_PROXY` 环境变量
   - 例如：`DOCKER_HTTP_PROXY=http://10.0.0.1:8080`
   - 这将在执行 Docker 命令时设置相应的代理环境变量

这些配置可以单独使用，也可以同时使用。在网络环境不佳或使用私有 Docker Registry 的情况下特别有用。

## 开发指南

### 前端开发

1. 启动开发服务器
   ```bash
   npm start
   ```

2. 进行修改，保存后自动刷新

### 后端开发

1. 安装开发依赖
   ```bash
   pip install -r requirements.txt
   ```

2. 启动后端服务（开发模式）
   ```bash
   cd backend
   python main.py
   ```

## API 端点

- `POST /api/pull-image`: 拉取 Docker 镜像并保存为 tar 文件
- `GET /api/pull-progress`: 获取镜像拉取进度
- `GET /api/downloaded-files`: 获取已下载文件列表
- `GET /api/download-file`: 下载指定文件
- `DELETE /api/clear-downloads`: 清空所有已下载文件

## 注意事项

- 应用需要访问 Docker daemon，确保当前用户有权限访问 Docker
- 在生产环境中，应该设置正确的 CORS 配置和安全措施
- 下载大型镜像可能需要较长时间和足够的磁盘空间

## 许可证

[MIT](LICENSE) 