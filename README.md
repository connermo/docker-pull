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

2. 使用自动部署脚本 (推荐)
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   
   这个脚本会自动完成前端构建和文件复制工作。

3. 或者手动步骤:
   - 安装前端依赖: `npm install`
   - 构建前端: `npm run build`
   - 复制前端文件到后端: `mkdir -p backend/static && cp -r build/* backend/static/`
   - 安装后端依赖: `cd backend && pip install -r requirements.txt`
   - 启动后端: `python main.py`

4. 访问应用程序
   浏览器打开 http://localhost:8000

### 使用 Docker 安装

1. 构建 Docker 镜像
   ```bash
   docker build -t docker-pull .
   ```

2. 运行容器
   ```bash
   # 创建下载目录
   mkdir -p ./downloads

   # 运行容器
   docker run -d \
     --name docker-pull \
     -p 8000:8000 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v $(pwd)/downloads:/app/backend/downloads \
     docker-pull
   ```

   带网络配置的示例：
   ```bash
   # 创建下载目录
   mkdir -p ./downloads

   # 运行容器
   docker run -d \
     --name docker-pull \
     -p 8000:8000 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v $(pwd)/downloads:/app/backend/downloads \
     -e DOCKER_REGISTRY_MIRROR=https://registry.docker-cn.com \
     -e DOCKER_HTTP_PROXY=http://proxy.example.com:8080 \
     -e DOCKER_HTTPS_PROXY=http://proxy.example.com:8080 \
     -e REACT_APP_AUTH_PASSWORD=your_custom_password \
     docker-pull
   ```

   使用 docker-compose 运行（推荐）：
   ```bash
   # 创建下载目录
   mkdir -p ./downloads

   # 启动服务
   docker-compose up -d
   ```

3. 访问应用程序
   浏览器打开 http://localhost:8000

### 目录说明

- `./downloads`: 下载的 Docker 镜像文件存储目录
  - 此目录会被挂载到容器内的 `/app/backend/downloads`
  - 即使容器被删除，下载的镜像文件也会保留
  - 建议定期清理此目录以节省磁盘空间

### 常见问题

1. **找不到 index.html 错误**
   - 错误消息: `RuntimeError: File at path /path/to/backend/static/index.html does not exist.`
   - 原因: 前端静态文件没有正确复制到后端静态目录
   - 解决方法: 
     ```bash
     mkdir -p backend/static
     cp -r build/* backend/static/
     ```
   - 使用 Docker 时，确保 Dockerfile 中正确复制了静态文件

2. **API接口404错误**
   - 原因: 前端可能使用了错误的API路径
   - 解决方法: 确保前端环境变量 `REACT_APP_API_URL` 设置为 `/api`

3. **下载目录权限问题**
   - 错误消息: `Permission denied` 或 `无法写入下载目录`
   - 原因: 容器内外的用户权限不匹配
   - 解决方法:
     ```bash
     # 确保下载目录有正确的权限
     chmod 777 ./downloads
     # 或者指定目录所有者
     sudo chown -R 1000:1000 ./downloads  # 1000 是容器内默认用户 ID
     ```

4. **磁盘空间不足**
   - 原因: 下载的镜像文件占用大量磁盘空间
   - 解决方法:
     ```bash
     # 查看下载目录大小
     du -sh ./downloads
     # 清理不需要的镜像文件
     rm ./downloads/*.tar
     # 或使用应用内的"清空所有"功能
     ```

## 环境变量配置

### 前端环境变量 (.env)
```
# API 接口地址（单端口模式下使用相对路径）
REACT_APP_API_URL=/api
# 静态资源路径
REACT_APP_STATIC_URL=/static
# 前端开发服务器端口（仅开发模式使用）
PORT=3000
# 前端访问密码
REACT_APP_AUTH_PASSWORD=admin123
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
DOCKER_REGISTRY_MIRROR=https://registry.docker-cn.com
# Docker HTTP 代理设置 (可选)
DOCKER_HTTP_PROXY=http://proxy.example.com:8080
# Docker HTTPS 代理设置 (可选)
DOCKER_HTTPS_PROXY=http://proxy.example.com:8080
```

### 单端口模式

该应用使用单端口模式，即前端和后端都通过同一个端口提供服务：

1. **工作原理**：
   - FastAPI 提供 API 服务 (`/api` 路径)
   - FastAPI 同时提供静态文件服务 (`/static` 和根路径)
   - 前端使用相对路径调用 API，无需指定主机和端口

2. **优势**：
   - 简化部署，只需暴露一个端口
   - 避免跨域问题
   - 更容易配置反向代理

3. **开发模式**：
   - 开发时前端和后端分别运行在不同端口
   - 构建后，前端静态文件会被复制到后端静态目录，通过后端服务器提供

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

### 安全性配置

应用包含一个简单的密码认证机制，防止未授权访问：

1. **密码认证**：
   - 首次访问应用需要输入密码
   - 默认密码为 `admin123`
   - 可通过环境变量 `REACT_APP_AUTH_PASSWORD` 自定义密码
   - 认证状态会保存在浏览器的 localStorage 中，刷新页面不需要重新认证

2. **安全建议**：
   - 生产环境中请务必修改默认密码
   - 考虑使用反向代理服务器提供更强的访问控制
   - 使用 HTTPS 保护数据传输安全 