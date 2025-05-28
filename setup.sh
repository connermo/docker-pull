#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== Docker镜像下载器 - 部署脚本 =====${NC}"

# 检查前端依赖
if [ ! -f "package.json" ]; then
    echo -e "${RED}错误: 未找到 package.json，请确保在项目根目录运行此脚本${NC}"
    exit 1
fi

# 检查后端依赖
if [ ! -f "backend/requirements.txt" ]; then
    echo -e "${RED}错误: 未找到 backend/requirements.txt，请确保在项目根目录运行此脚本${NC}"
    exit 1
fi

# 安装前端依赖
echo -e "${YELLOW}步骤 1/5: 安装前端依赖${NC}"
npm install
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 安装前端依赖失败${NC}"
    exit 1
fi

# 构建前端
echo -e "${YELLOW}步骤 2/5: 构建前端${NC}"
npm run build
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 构建前端失败${NC}"
    exit 1
fi

# 创建后端静态目录
echo -e "${YELLOW}步骤 3/5: 创建后端静态目录${NC}"
mkdir -p backend/static
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 创建后端静态目录失败${NC}"
    exit 1
fi

# 复制前端构建文件到后端静态目录
echo -e "${YELLOW}步骤 4/5: 复制前端文件到后端静态目录${NC}"
cp -r build/* backend/static/
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 复制前端文件失败${NC}"
    exit 1
fi

# 安装后端依赖
echo -e "${YELLOW}步骤 5/5: 安装后端依赖${NC}"
cd backend
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 安装后端依赖失败${NC}"
    exit 1
fi

echo -e "${GREEN}====== 部署成功! ======${NC}"
echo -e "运行以下命令启动应用:"
echo -e "${YELLOW}cd backend && python main.py${NC}"
echo -e "然后访问: http://localhost:8000" 