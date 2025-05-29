# Docker Pull Web Application

一个基于 Web 的 Docker 镜像拉取工具，支持企业级代理配置。

## ⚡ 快速开始

### 1行命令启动：

```bash
# 创建并启动（自动下载配置文件）
curl -sSL https://raw.githubusercontent.com/connermo/docker-pull/main/docker-compose.yml > docker-compose.yml && docker-compose up -d
```

🎉 **就这么简单！** 访问 `http://localhost:8000` 开始使用。

### 或者手动创建：

```bash
# 1. 创建 docker-compose.yml
cat > docker-compose.yml << 'EOF'
services:
  app:
    image: connermo/docker-pull:latest
    ports:
      - "8000:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./downloads:/app/backend/downloads
    environment:
      - DOCKER_PROXY=${DOCKER_PROXY:-}
      - DOCKER_REGISTRY_MIRROR=${DOCKER_REGISTRY_MIRROR:-}
    restart: unless-stopped

networks:
  default:
    driver: bridge
EOF

# 2. 启动应用
docker-compose up -d
```

> 💡 **无需克隆项目**，直接使用预构建镜像！

## 🚀 功能特点

- 🐳 通过 Web 界面拉取 Docker 镜像
- 📦 支持多种导出格式（tar.gz, tar, 目录）
- 🔍 镜像信息查看和验证
- 📁 文件管理和下载功能
- ⚙️ 简单的代理配置支持

## 📋 代理配置（可选）

### 方式1：命令行设置（推荐）

```bash
# 使用代理启动
DOCKER_PROXY=http://proxy.company.com:8080 docker-compose up -d

# 需要认证的代理
DOCKER_PROXY=http://username:password@proxy.company.com:8080 docker-compose up -d
```

### 方式2：环境变量文件

如果需要持久化配置，创建 `.env` 文件：

```bash
# 创建 .env 文件
cat > .env << 'EOF'
DOCKER_PROXY=http://proxy.company.com:8080
DOCKER_REGISTRY_MIRROR=https://mirror.aliyuncs.com
EOF

# 启动应用
docker-compose up -d
```

### 配置示例

**默认配置（不使用代理）**：
```bash
docker-compose up -d
```

**企业内网（需要代理）**：
```bash
DOCKER_PROXY=http://proxy.company.com:8080 docker-compose up -d
```

**需要认证的代理**：
```bash
DOCKER_PROXY=http://username:password@proxy.company.com:8080 docker-compose up -d
```

### 配置选项

| 变量 | 说明 | 示例 |
|------|------|------|
| `DOCKER_PROXY` | 代理地址（可选） | `http://proxy.company.com:8080` |
| `DOCKER_REGISTRY_MIRROR` | 镜像加速（可选） | `https://mirror.aliyuncs.com` |

### 快速设置

也可以直接在命令行设置：

```bash
# 使用代理启动
DOCKER_PROXY=http://proxy.company.com:8080 docker-compose up -d

# 不使用代理启动
docker-compose up -d
```

## 🛠️ 常用命令

```bash
# 启动应用
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止应用
docker-compose down

# 查看当前配置
docker-compose config | grep -i proxy
```

## 🌐 使用方法

1. **启动应用**：`docker-compose up -d`
2. **访问界面**：`http://localhost:8000`
3. **拉取镜像**：输入镜像名称（如：`nginx:latest`），选择格式，点击拉取

## 🚨 故障排除

```bash
# 查看容器日志
docker-compose logs app

# 重启容器
docker-compose restart

# 检查代理配置
docker-compose config | grep -i proxy
```

## 💡 说明

- 使用预构建镜像 `connermo/docker-pull:latest`
- 系统会自动从 `DOCKER_PROXY` 生成所需的环境变量
- 容器内的Docker命令直接使用标准环境变量
- 如果不需要代理，保持 `DOCKER_PROXY` 注释状态即可

---

**快速开始**: `docker-compose up -d` → 访问 `http://localhost:8000` 🚀