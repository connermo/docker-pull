from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import os
import tempfile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import logging
import json
import shutil
import time
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 模型定义
class ImageRequest(BaseModel):
    image_name: str

class DownloadedFile(BaseModel):
    name: str
    size: int
    created_at: str
    path: str

app = FastAPI()

# 从环境变量获取配置
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
DOWNLOADS_DIR_ENV = os.getenv("DOWNLOADS_DIR")
DOCKER_REGISTRY_MIRROR = os.getenv("DOCKER_REGISTRY_MIRROR")
DOCKER_HTTP_PROXY = os.getenv("DOCKER_HTTP_PROXY")
DOCKER_HTTPS_PROXY = os.getenv("DOCKER_HTTPS_PROXY")

# Docker命令执行函数
def run_docker_command(command):
    try:
        logger.info(f"执行Docker命令: {' '.join(command)}")
        env = os.environ.copy()
        
        # 添加代理环境变量
        if DOCKER_HTTP_PROXY:
            env["HTTP_PROXY"] = DOCKER_HTTP_PROXY
            env["http_proxy"] = DOCKER_HTTP_PROXY
        if DOCKER_HTTPS_PROXY:
            env["HTTPS_PROXY"] = DOCKER_HTTPS_PROXY
            env["https_proxy"] = DOCKER_HTTPS_PROXY
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        logger.info(f"Docker命令输出: {result.stdout}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker命令执行失败: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Docker命令执行失败: {e.stderr}")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建必要的目录
DOWNLOADS_DIR = DOWNLOADS_DIR_ENV or os.path.join(os.path.dirname(__file__), "downloads")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# 记录目录信息
logger.info(f"下载目录: {os.path.abspath(DOWNLOADS_DIR)}")
logger.info(f"静态文件目录: {os.path.abspath(STATIC_DIR)}")

# 检查静态文件是否存在
index_html_path = os.path.join(STATIC_DIR, "index.html")
if os.path.exists(index_html_path):
    logger.info(f"找到index.html: {index_html_path}")
else:
    logger.warning(f"找不到index.html: {index_html_path}")
    # 尝试在上一级目录查找
    parent_static = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    parent_index = os.path.join(parent_static, "index.html")
    if os.path.exists(parent_index):
        logger.info(f"在上级目录找到index.html: {parent_index}")
        # 如果在上级目录找到，则使用上级目录
        STATIC_DIR = parent_static
        index_html_path = parent_index
        logger.info(f"更新静态文件目录为: {STATIC_DIR}")
    
    # 列出静态目录中的文件
    if os.path.exists(STATIC_DIR):
        files = os.listdir(STATIC_DIR)
        logger.info(f"静态目录中的文件: {files if files else '(空)'}")
        # 如果有static子目录，列出它的内容
        static_subdir = os.path.join(STATIC_DIR, "static")
        if os.path.exists(static_subdir) and os.path.isdir(static_subdir):
            subfiles = os.listdir(static_subdir)
            logger.info(f"static子目录中的文件: {subfiles if subfiles else '(空)'}")

# 挂载静态文件目录到 /static 路径
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 添加根路径重定向到前端应用
@app.get("/")
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        # 如果index.html不存在，返回一个简单的页面
        logger.error(f"找不到index.html文件: {index_path}")
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Docker镜像下载器</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }
                h1 { color: #333; }
                .error { color: #e74c3c; background: #fadbd8; padding: 10px; border-radius: 5px; }
                .info { margin-top: 20px; background: #f8f9fa; padding: 15px; border-radius: 5px; }
                code { background: #eee; padding: 2px 5px; border-radius: 3px; font-family: monospace; }
            </style>
        </head>
        <body>
            <h1>Docker镜像下载器</h1>
            <div class="error">
                <h2>配置错误</h2>
                <p>找不到前端静态文件。请确保前端已正确构建并复制到静态目录。</p>
            </div>
            <div class="info">
                <h3>排查步骤：</h3>
                <ol>
                    <li>确保前端构建成功: <code>npm run build</code></li>
                    <li>确保静态文件已复制到后端: <code>cp -r build/* backend/static/</code></li>
                    <li>检查Dockerfile中的复制命令是否正确</li>
                    <li>重新构建并运行容器</li>
                </ol>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)
    
    return FileResponse(index_path)

# 重新定义所有API端点为直接的app路由，避免FastAPI子应用的问题
@app.get("/api/downloaded-files")
async def api_get_downloaded_files():
    logger.info("直接调用 /api/downloaded-files 端点")
    try:
        files = []
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar'):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                stat = os.stat(file_path)
                files.append(DownloadedFile(
                    name=filename,
                    size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    path=file_path
                ))
        return sorted(files, key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

@app.get("/api/download-file")
async def api_download_file(path: str):
    logger.info(f"直接调用 /api/download-file 端点，路径: {path}")
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 确保文件在downloads目录中
        if not os.path.abspath(path).startswith(os.path.abspath(DOWNLOADS_DIR)):
            raise HTTPException(status_code=403, detail="无权访问该文件")
            
        return FileResponse(
            path,
            media_type='application/octet-stream',
            filename=os.path.basename(path)
        )
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

@app.delete("/api/clear-downloads")
async def api_clear_downloads():
    logger.info("直接调用 /api/clear-downloads 端点")
    try:
        logger.info("开始清空下载目录")
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar'):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                try:
                    os.remove(file_path)
                    logger.info(f"已删除文件: {filename}")
                except Exception as e:
                    logger.error(f"删除文件 {filename} 失败: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
        return {"message": "所有文件已清空"}
    except Exception as e:
        logger.error(f"清空下载目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清空下载目录失败: {str(e)}")

@app.get("/api/pull-progress")
async def api_get_pull_progress(image_name: str):
    logger.info(f"直接调用 /api/pull-progress 端点，镜像: {image_name}")
    try:
        # 获取镜像拉取进度
        pull_cmd = ["docker", "pull"]
        
        # 如果配置了镜像仓库镜像，则添加相关参数
        if DOCKER_REGISTRY_MIRROR:
            pull_cmd.extend(["--registry-mirror", DOCKER_REGISTRY_MIRROR])
            
        pull_cmd.append(image_name)
        
        env = os.environ.copy()
        # 添加代理环境变量
        if DOCKER_HTTP_PROXY:
            env["HTTP_PROXY"] = DOCKER_HTTP_PROXY
            env["http_proxy"] = DOCKER_HTTP_PROXY
        if DOCKER_HTTPS_PROXY:
            env["HTTPS_PROXY"] = DOCKER_HTTPS_PROXY
            env["https_proxy"] = DOCKER_HTTPS_PROXY
            
        result = subprocess.run(
            pull_cmd,
            capture_output=True,
            text=True,
            env=env
        )
        
        # 解析输出以获取进度信息
        output = result.stdout
        if "Downloading" in output:
            # 这里可以添加更复杂的进度解析逻辑
            return {"status": "downloading", "progress": 50}
        elif "Download complete" in output:
            return {"status": "complete", "progress": 100}
        else:
            return {"status": "unknown", "progress": 0}
            
    except Exception as e:
        logger.error(f"获取进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")

@app.post("/api/pull-image")
async def api_pull_image(request: ImageRequest):
    logger.info(f"直接调用 /api/pull-image 端点，镜像: {request.image_name}")
    try:
        logger.info(f"开始拉取镜像: {request.image_name}")
        
        # 构建文件名，确保合法
        safe_image_name = request.image_name.replace('/', '_').replace(':', '_')
        file_path = os.path.join(DOWNLOADS_DIR, f"{safe_image_name}.tar")
        logger.info(f"文件路径: {file_path}")
        
        # 如果文件已存在，直接返回
        if os.path.exists(file_path):
            logger.info(f"文件已存在，直接返回: {file_path}")
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=f"{safe_image_name}.tar"
            )
        
        # 拉取镜像
        logger.info("正在拉取镜像...")
        pull_cmd = ["docker", "pull"]
        
        # 如果配置了镜像仓库镜像，则添加相关参数
        if DOCKER_REGISTRY_MIRROR:
            logger.info(f"使用镜像仓库镜像: {DOCKER_REGISTRY_MIRROR}")
            pull_cmd.extend(["--registry-mirror", DOCKER_REGISTRY_MIRROR])
        
        pull_cmd.append(request.image_name)
        run_docker_command(pull_cmd)
        
        # 保存镜像为tar文件
        logger.info("正在保存镜像...")
        run_docker_command(["docker", "save", "-o", file_path, request.image_name])
        
        # 确保文件存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail=f"文件创建失败: {file_path}")
            
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise HTTPException(status_code=500, detail="保存的文件大小为0")
            
        logger.info(f"镜像保存完成，文件大小: {file_size} 字节")
        
        # 返回文件
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=f"{safe_image_name}.tar"
        )
            
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

# 确保其他HTML路由也能正确返回前端页面（支持前端路由）
@app.get("/{catch_all:path}")
async def catch_all(catch_all: str):
    # 如果是API路由，则跳过此处理器
    if catch_all.startswith("api/"):
        raise HTTPException(status_code=404, detail="API路径不存在")
    
    # 检查是否存在对应的静态文件
    file_path = os.path.join(STATIC_DIR, catch_all)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        logger.info(f"提供静态文件: {file_path}")
        return FileResponse(file_path)
    
    # 否则返回index.html（让前端路由处理）
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        logger.error(f"找不到index.html文件: {index_path}")
        raise HTTPException(status_code=500, detail="前端静态文件未找到，请检查配置")
    
    logger.info(f"前端路由: {catch_all} -> index.html")
    return FileResponse(index_path)

# 创建API路由前缀
api_router = FastAPI()

@api_router.get("/downloaded-files")
async def get_downloaded_files() -> List[DownloadedFile]:
    try:
        files = []
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar'):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                stat = os.stat(file_path)
                files.append(DownloadedFile(
                    name=filename,
                    size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    path=file_path
                ))
        return sorted(files, key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

@api_router.get("/download-file")
async def download_file(path: str):
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 确保文件在downloads目录中
        if not os.path.abspath(path).startswith(os.path.abspath(DOWNLOADS_DIR)):
            raise HTTPException(status_code=403, detail="无权访问该文件")
            
        return FileResponse(
            path,
            media_type='application/octet-stream',
            filename=os.path.basename(path)
        )
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

@api_router.post("/pull-image")
async def pull_image(request: ImageRequest):
    try:
        logger.info(f"开始拉取镜像: {request.image_name}")
        
        # 构建文件名，确保合法
        safe_image_name = request.image_name.replace('/', '_').replace(':', '_')
        file_path = os.path.join(DOWNLOADS_DIR, f"{safe_image_name}.tar")
        logger.info(f"文件路径: {file_path}")
        
        # 如果文件已存在，直接返回
        if os.path.exists(file_path):
            logger.info(f"文件已存在，直接返回: {file_path}")
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=f"{safe_image_name}.tar"
            )
        
        # 拉取镜像
        logger.info("正在拉取镜像...")
        pull_cmd = ["docker", "pull"]
        
        # 如果配置了镜像仓库镜像，则添加相关参数
        if DOCKER_REGISTRY_MIRROR:
            logger.info(f"使用镜像仓库镜像: {DOCKER_REGISTRY_MIRROR}")
            pull_cmd.extend(["--registry-mirror", DOCKER_REGISTRY_MIRROR])
        
        pull_cmd.append(request.image_name)
        run_docker_command(pull_cmd)
        
        # 保存镜像为tar文件
        logger.info("正在保存镜像...")
        run_docker_command(["docker", "save", "-o", file_path, request.image_name])
        
        # 确保文件存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail=f"文件创建失败: {file_path}")
            
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise HTTPException(status_code=500, detail="保存的文件大小为0")
            
        logger.info(f"镜像保存完成，文件大小: {file_size} 字节")
        
        # 返回文件
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=f"{safe_image_name}.tar"
        )
            
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@api_router.get("/pull-progress")
async def get_pull_progress(image_name: str):
    try:
        # 获取镜像拉取进度
        pull_cmd = ["docker", "pull"]
        
        # 如果配置了镜像仓库镜像，则添加相关参数
        if DOCKER_REGISTRY_MIRROR:
            pull_cmd.extend(["--registry-mirror", DOCKER_REGISTRY_MIRROR])
            
        pull_cmd.append(image_name)
        
        env = os.environ.copy()
        # 添加代理环境变量
        if DOCKER_HTTP_PROXY:
            env["HTTP_PROXY"] = DOCKER_HTTP_PROXY
            env["http_proxy"] = DOCKER_HTTP_PROXY
        if DOCKER_HTTPS_PROXY:
            env["HTTPS_PROXY"] = DOCKER_HTTPS_PROXY
            env["https_proxy"] = DOCKER_HTTPS_PROXY
            
        result = subprocess.run(
            pull_cmd,
            capture_output=True,
            text=True,
            env=env
        )
        
        # 解析输出以获取进度信息
        output = result.stdout
        if "Downloading" in output:
            # 这里可以添加更复杂的进度解析逻辑
            return {"status": "downloading", "progress": 50}
        elif "Download complete" in output:
            return {"status": "complete", "progress": 100}
        else:
            return {"status": "unknown", "progress": 0}
            
    except Exception as e:
        logger.error(f"获取进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")

@api_router.delete("/clear-downloads")
async def clear_downloads():
    try:
        logger.info("开始清空下载目录")
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar'):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                try:
                    os.remove(file_path)
                    logger.info(f"已删除文件: {filename}")
                except Exception as e:
                    logger.error(f"删除文件 {filename} 失败: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
        return {"message": "所有文件已清空"}
    except Exception as e:
        logger.error(f"清空下载目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清空下载目录失败: {str(e)}")

# 将API路由添加到主应用，带前缀
app.mount("/api", api_router)

# 打印所有注册的路由，便于调试
logger.info("已注册的API路由:")
for route in api_router.routes:
    logger.info(f"  - {route.path} [{', '.join(route.methods)}]")

logger.info(f"下载目录已创建: {DOWNLOADS_DIR}")
logger.info("API路由已挂载到 /api 前缀")

if __name__ == "__main__":
    import uvicorn
    # 使用环境变量中的主机和端口
    logger.info(f"启动服务 - 主机: {API_HOST}, 端口: {API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT) 