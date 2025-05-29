# Docker Pull 快速配置指南 ⚡

## 🎯 1行命令启动

```bash
# 下载配置并启动
curl -sSL https://raw.githubusercontent.com/connermo/docker-pull/main/docker-compose.yml > docker-compose.yml && docker-compose up -d
```

**或者手动创建：**

```bash
# 创建配置文件
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

# 启动应用
docker-compose up -d
```

完成！🎉

**可选**：如果需要代理，直接命令行设置：
```bash
DOCKER_PROXY=http://proxy.company.com:8080 docker-compose up -d
```

---

## 📖 配置示例

**默认配置（不使用代理）**：
```env
# DOCKER_PROXY=
# DOCKER_REGISTRY_MIRROR=https://mirror.aliyuncs.com
```

**企业内网（需要代理）**：
```env
DOCKER_PROXY=http://proxy.company.com:8080
DOCKER_REGISTRY_MIRROR=https://mirror.aliyuncs.com
```

**需要认证的代理**：
```env
DOCKER_PROXY=http://username:password@proxy.company.com:8080
```

**超级快速设置**：
```bash
# 直接在命令行设置代理
DOCKER_PROXY=http://proxy.company.com:8080 docker-compose up -d
```

---

## 🛠️ 配置选项

| 参数 | 说明 | 示例 |
|-----|------|------|
| `DOCKER_PROXY` | 代理地址（可选） | `http://proxy.company.com:8080` |
| `DOCKER_REGISTRY_MIRROR` | 镜像加速（可选） | `https://mirror.aliyuncs.com` |

---

## 🔍 验证和测试

```bash
# 查看当前配置
docker-compose config | grep -i proxy

# 查看容器日志
docker-compose logs app

# 查看运行状态
docker-compose ps
```

---

## 💡 说明

- **使用预构建镜像**：`connermo/docker-pull:latest`
- **默认不使用代理**：适合大多数家庭和直连网络环境
- 系统会自动从 `DOCKER_PROXY` 生成 `HTTP_PROXY`、`http_proxy` 等环境变量
- 容器内的Docker命令直接使用这些环境变量
- 如果不需要代理，保持 `DOCKER_PROXY` 注释状态即可 