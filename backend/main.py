from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import os
import tempfile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
import logging
import json
import shutil
import time
from typing import Optional, List, Dict
from datetime import datetime
from dotenv import load_dotenv
from fastapi import APIRouter
import docker
import asyncio
from concurrent.futures import ThreadPoolExecutor
import gzip
import signal
import sys
import concurrent.futures
import uvicorn

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Docker客户端延迟初始化
docker_client = None

def get_docker_client():
    """获取Docker客户端实例，延迟初始化"""
    global docker_client
    if docker_client is None:
        try:
            # 备份当前环境变量
            original_env = os.environ.copy()
            
            # 临时清理可能影响Docker客户端连接的环境变量
            temp_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'DOCKER_HOST']
            for var in temp_vars_to_clear:
                if var in os.environ:
                    del os.environ[var]
            
            try:
                # 尝试连接到Docker daemon
                docker_client = docker.from_env()
                logger.info("Docker客户端初始化成功")
            finally:
                # 恢复环境变量
                os.environ.clear()
                os.environ.update(original_env)
                
        except Exception as e:
            logger.error(f"Docker客户端初始化失败: {e}")
            # 尝试手动指定socket路径
            try:
                docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
                logger.info("使用unix socket初始化Docker客户端成功")
            except Exception as e2:
                logger.error(f"使用unix socket初始化Docker客户端也失败: {e2}")
                raise e2
    return docker_client

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

# 新的代理配置
DOCKER_PROXY = os.getenv("DOCKER_PROXY")

# 压缩方法配置
COMPRESSION_METHOD = {
    "name": "pigz",
    "ext": ".tar.gz", 
    "command": ["pigz", "--fast", "-p", "4", "-c"],  # 限制使用4个CPU核心
    "decompress": ["pigz", "-d", "-c"]
}

# 从环境变量获取压缩超时设置（默认2小时）
COMPRESSION_TIMEOUT = int(os.getenv("COMPRESSION_TIMEOUT", "7200"))
DOCKER_SAVE_TIMEOUT = int(os.getenv("DOCKER_SAVE_TIMEOUT", "3600"))

def check_pigz_support():
    """检查 pigz 是否可用"""
    try:
        subprocess.run(["pigz", "--version"], 
                     capture_output=True, check=True, timeout=5)
        logger.info("pigz 高速压缩工具可用")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("pigz 不可用，将使用 Python 内置 gzip")
        return False

# 检查 pigz 支持
PIGZ_AVAILABLE = check_pigz_support()

# Docker命令执行函数
def run_docker_command(command, stream_output=False):
    try:
        logger.info(f"执行Docker命令: {' '.join(command)}")
        env = os.environ.copy()
        
        # 添加代理环境变量
        if DOCKER_PROXY:
            env["HTTP_PROXY"] = DOCKER_PROXY
            env["http_proxy"] = DOCKER_PROXY
            env["HTTPS_PROXY"] = DOCKER_PROXY
            env["https_proxy"] = DOCKER_PROXY
        
        if stream_output:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
                universal_newlines=True
            )
            return process
        else:
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

# 创建 API 路由
api_router = APIRouter(prefix="/api")

# 用于存储下载进度的全局字典
download_progress: Dict[str, Dict] = {}

# 用于存储下载任务的全局字典
download_tasks: Dict[str, asyncio.Task] = {}

async def pull_image_with_progress(image_name: str):
    """使用 Docker SDK 拉取镜像并跟踪进度"""
    try:
        # 初始化进度
        download_progress[image_name] = {
            "status": "starting",
            "progress": 0,
            "detail": "准备开始下载...",
            "output": [],
            "layers": {}  # 存储每个层的进度
        }
        
        def add_log(message: str):
            """添加日志到输出并记录到控制台"""
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_message = f"[{timestamp}] {message}"
            download_progress[image_name]["output"].append(log_message)
            logger.info(f"下载进度: {message}")
            # 限制输出行数，避免内存溢出
            if len(download_progress[image_name]["output"]) > 200:
                download_progress[image_name]["output"] = download_progress[image_name]["output"][-150:]
        
        add_log("开始准备下载...")
        
        # 添加一个小延迟，确保前端能获取到初始状态
        await asyncio.sleep(0.5)
        
        # 获取最佳压缩方法
        compression_method = get_compression_method()
        method_name, method_config = compression_method
        
        # 构建保存路径
        filename = f"{image_name.replace('/', '_').replace(':', '_')}{method_config['ext']}"
        save_path = os.path.join(DOWNLOADS_DIR, filename)
        
        add_log(f"使用压缩方法: {method_name}")
        add_log(f"目标文件: {filename}")
        
        # 更新状态
        download_progress[image_name]["status"] = "downloading"
        download_progress[image_name]["detail"] = "正在检查镜像..."
        add_log(f"开始拉取镜像: {image_name}")
        
        # 获取镜像信息
        try:
            image = get_docker_client().images.get(image_name)
            download_progress[image_name]["detail"] = "镜像已存在本地"
            download_progress[image_name]["status"] = "downloading"
            download_progress[image_name]["progress"] = 30
            add_log("镜像已存在本地，跳过下载步骤")
            await asyncio.sleep(1)
            
            download_progress[image_name]["detail"] = "跳过下载，开始保存镜像..."
            download_progress[image_name]["progress"] = 60
            add_log("开始保存已存在的镜像到文件")
            await asyncio.sleep(1)
        except docker.errors.ImageNotFound:
            # 镜像不存在，需要下载
            download_progress[image_name]["detail"] = "镜像不存在本地，开始从远程下载..."
            download_progress[image_name]["progress"] = 5
            add_log("镜像不存在本地，开始从远程仓库下载")
            await asyncio.sleep(0.5)
            
            # 拉取镜像并跟踪进度
            layer_count = 0
            total_layers = 0
            completed_layers = 0
            
            add_log("连接到Docker仓库，开始拉取镜像层...")
            
            for line in get_docker_client().api.pull(image_name, stream=True, decode=True):
                if 'id' in line and 'status' in line:
                    layer_id = line['id']
                    status = line['status']
                    
                    # 统计总层数
                    if layer_id not in download_progress[image_name]["layers"]:
                        download_progress[image_name]["layers"][layer_id] = {
                            "status": status,
                            "progress": 0
                        }
                        total_layers += 1
                        if status == "Pulling fs layer":
                            add_log(f"发现新层 {layer_id}: 开始拉取")
                    
                    # 更新层状态
                    download_progress[image_name]["layers"][layer_id]["status"] = status
                    
                    # 解析进度信息
                    progress_info = ""
                    if 'progressDetail' in line:
                        detail = line['progressDetail']
                        if 'current' in detail and 'total' in detail:
                            current = detail['current']
                            total = detail['total']
                            if total > 0:
                                progress = (current / total) * 100
                                download_progress[image_name]["layers"][layer_id]["progress"] = int(progress)
                                # 格式化字节大小
                                current_mb = current / (1024 * 1024)
                                total_mb = total / (1024 * 1024)
                                progress_info = f" ({current_mb:.1f}MB/{total_mb:.1f}MB, {progress:.1f}%)"
                    
                    # 如果层完成了
                    if status in ['Pull complete', 'Already exists']:
                        download_progress[image_name]["layers"][layer_id]["progress"] = 100
                        if status == 'Pull complete':
                            completed_layers += 1
                            add_log(f"层 {layer_id}: 下载完成")
                        elif status == 'Already exists':
                            add_log(f"层 {layer_id}: 已存在，跳过下载")
                    elif status == 'Downloading':
                        if progress_info:
                            add_log(f"层 {layer_id}: 下载中{progress_info}")
                    elif status == 'Extracting':
                        if progress_info:
                            add_log(f"层 {layer_id}: 解压中{progress_info}")
                        elif 'progress' in line:
                            add_log(f"层 {layer_id}: 解压中 - {line['progress']}")
                    elif status == 'Verifying Checksum':
                        add_log(f"层 {layer_id}: 验证校验和")
                    elif status == 'Download complete':
                        add_log(f"层 {layer_id}: 下载完成，开始解压")
                    
                    # 计算总体进度 (下载阶段占60%)
                    if total_layers > 0:
                        layer_progress = sum(layer["progress"] for layer in download_progress[image_name]["layers"].values())
                        overall_progress = int((layer_progress / (total_layers * 100)) * 60)
                        download_progress[image_name]["progress"] = max(5, overall_progress)
                    
                    # 更新详细信息
                    status_msg = f"层 {layer_id}: {status}"
                    if 'progress' in line:
                        status_msg += f" - {line['progress']}"
                    download_progress[image_name]["detail"] = status_msg
                    
                    # 添加小延迟，让前端有时间获取进度
                    await asyncio.sleep(0.1)
            
            add_log(f"所有层下载完成！共处理 {total_layers} 个层")
        
        # 更新状态为保存中
        download_progress[image_name]["status"] = "saving"
        download_progress[image_name]["detail"] = f"正在保存到: {filename}"
        download_progress[image_name]["progress"] = 70
        add_log(f"开始保存镜像到文件: {filename}")
        await asyncio.sleep(0.5)
        
        # 更新压缩进度
        download_progress[image_name]["detail"] = f"正在使用 {method_name} 压缩镜像数据..."
        download_progress[image_name]["progress"] = 80
        add_log(f"使用高速压缩方法: {method_name}")
        await asyncio.sleep(0.5)
        
        # 在线程池中执行同步的保存操作
        def save_image():
            """保存镜像到压缩文件"""
            try:
                # 使用临时文件避免磁盘空间问题
                with tempfile.NamedTemporaryFile(delete=False) as temp_tar:
                    temp_tar_path = temp_tar.name
                    try:
                        # 先保存为tar到临时文件，带超时控制
                        start_time = time.time()
                        for chunk in get_docker_client().images.get(image_name).save():
                            # 检查Docker保存操作是否超时
                            if time.time() - start_time > DOCKER_SAVE_TIMEOUT:
                                raise TimeoutError(f"Docker保存操作超时（{DOCKER_SAVE_TIMEOUT}秒）")
                            temp_tar.write(chunk)
                        temp_tar.flush()
                        temp_tar.close()
                        
                        # 根据压缩方法进行压缩
                        if method_name == "pigz":
                            # 创建一个进度更新函数，接收当前的download_progress字典
                            def make_progress_updater(progress_dict):
                                def update_compression_progress(progress):
                                    progress_dict[image_name]["progress"] = 80 + int(progress * 0.15)  # 80-95%
                                    progress_dict[image_name]["detail"] = f"压缩进度: {progress}%"
                                return update_compression_progress
                            
                            compress_with_pigz(
                                open(temp_tar_path, 'rb'),
                                save_path,
                                progress_callback=make_progress_updater(download_progress)
                            )
                        else:
                            # 使用 Python 内置 gzip (降级方案)
                            with gzip.open(save_path, 'wb') as gz_file:
                                shutil.copyfileobj(open(temp_tar_path, 'rb'), gz_file)
                    finally:
                        # 清理临时文件
                        try:
                            os.unlink(temp_tar_path)
                        except:
                            pass
                        
            except Exception as e:
                if isinstance(e, TimeoutError):
                    raise Exception(f"操作超时: {str(e)}")
                elif isinstance(e, subprocess.CalledProcessError):
                    raise Exception(f"压缩失败: {str(e)}")
                else:
                    raise Exception(f"保存镜像失败: {str(e)}")
        
        # 使用线程池执行保存操作
        with ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(executor, save_image)
        
        download_progress[image_name]["progress"] = 95
        download_progress[image_name]["detail"] = "保存完成，正在验证文件..."
        add_log("镜像保存完成，验证文件完整性...")
        await asyncio.sleep(0.5)
        
        # 验证文件
        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path)
            file_size_mb = file_size / (1024 * 1024)
            add_log(f"文件验证成功！文件大小: {file_size_mb:.1f}MB")
        
        # 更新最终状态
        download_progress[image_name]["status"] = "complete"
        download_progress[image_name]["detail"] = "下载完成"
        download_progress[image_name]["progress"] = 100
        add_log(f"镜像 {image_name} 下载并保存完成！")
        
        return {"status": "success", "message": "镜像拉取并保存成功"}
        
    except Exception as e:
        error_msg = f"拉取镜像失败: {str(e)}"
        logger.error(error_msg)
        download_progress[image_name]["status"] = "error"
        download_progress[image_name]["detail"] = str(e)
        download_progress[image_name]["output"].append(f"[错误] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

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

@api_router.post("/pull-image")
async def pull_image(request: ImageRequest):
    """启动异步下载任务"""
    try:
        # 如果已经有相同的下载任务在运行，返回错误
        if request.image_name in download_tasks and not download_tasks[request.image_name].done():
            raise HTTPException(status_code=400, detail="该镜像正在下载中")
        
        # 创建新的下载任务
        task = asyncio.create_task(pull_image_with_progress(request.image_name))
        download_tasks[request.image_name] = task
        
        return {"status": "started", "message": "开始下载镜像"}
    except Exception as e:
        logger.error(f"启动下载任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pull-progress")
async def get_pull_progress(image_name: str):
    try:
        if image_name not in download_progress:
            return {
                "status": "not_found",
                "progress": 0,
                "detail": "未找到下载任务",
                "output": []
            }
        return download_progress[image_name]
    except Exception as e:
        logger.error(f"获取进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")

@api_router.get("/downloaded-files")
async def list_downloaded_files():
    try:
        files = []
        # 只支持 .tar.gz 文件（pigz 压缩）
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar.gz'):
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

@api_router.delete("/clear-downloads")
async def clear_downloads():
    try:
        # 只删除 .tar.gz 文件
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith('.tar.gz'):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                os.remove(file_path)
                logger.info(f"已删除文件: {file_path}")
        return {"status": "success", "message": "所有文件已清空"}
    except Exception as e:
        logger.error(f"清空文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清空文件失败: {str(e)}")

@api_router.get("/download-file")
async def download_file(path: str):
    try:
        # 验证文件路径是否在下载目录内
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(os.path.abspath(DOWNLOADS_DIR)):
            raise HTTPException(status_code=400, detail="无效的文件路径")
        
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 获取文件名
        filename = os.path.basename(abs_path)
        
        # 使用流式响应返回文件
        return FileResponse(
            abs_path,
            filename=filename,
            media_type='application/octet-stream',
            background=None  # 禁用后台任务，避免文件被过早关闭
        )
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

# 将 api_router 挂载到主应用
app.include_router(api_router)

# 打印所有注册的路由，便于调试
logger.info("已注册的API路由:")
for route in app.routes:
    if hasattr(route, 'methods'):
        logger.info(f"  - {route.path} [{', '.join(route.methods)}]")
    else:
        logger.info(f"  - {route.path} [Mount]")

logger.info(f"下载目录已创建: {DOWNLOADS_DIR}")
logger.info("API路由已挂载到 /api 前缀")

def get_compression_method():
    """获取压缩方法"""
    if PIGZ_AVAILABLE:
        return "pigz", COMPRESSION_METHOD
    else:
        # 如果 pigz 不可用，使用 Python 内置 gzip
        return "gzip", {"name": "gzip", "ext": ".tar.gz", "command": None}

def compress_with_pigz(input_stream, output_path, progress_callback=None):
    """使用 pigz 进行高速并行压缩，带超时控制和进度反馈
    
    Args:
        input_stream: 输入流
        output_path: 输出文件路径
        progress_callback: 可选的进度回调函数，接收压缩进度（0-100）
    """
    if not PIGZ_AVAILABLE:
        # 使用 Python 内置 gzip
        with gzip.open(output_path, 'wb') as gz_file:
            shutil.copyfileobj(input_stream, gz_file)
        return
    
    # 获取输入流大小用于进度计算
    input_size = 0
    if hasattr(input_stream, 'seek') and hasattr(input_stream, 'tell'):
        current_pos = input_stream.tell()
        input_stream.seek(0, 2)  # 移动到文件末尾
        input_size = input_stream.tell()
        input_stream.seek(current_pos)  # 恢复位置
    
    # 使用 pigz 进行并行压缩，限制CPU核心数
    cmd = ["pigz", "--fast", "-p", "4", "-c"]
    temp_output = output_path + ".tmp"
    
    try:
        with open(temp_output, 'wb') as outfile:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=outfile,
                stderr=subprocess.PIPE,
                bufsize=1024*1024  # 1MB缓冲区
            )
            
            # 启动进度监控线程
            if input_size > 0 and progress_callback:
                def monitor_progress():
                    while process.poll() is None:
                        try:
                            if hasattr(input_stream, 'tell'):
                                current_pos = input_stream.tell()
                                progress = min(100, int((current_pos / input_size) * 100))
                                progress_callback(progress)
                            time.sleep(1)  # 每秒更新一次进度
                        except Exception:
                            pass
                
                import threading
                progress_thread = threading.Thread(target=monitor_progress, daemon=True)
                progress_thread.start()
            
            # 使用超时控制复制数据
            start_time = time.time()
            bytes_copied = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            
            while True:
                # 检查是否超时
                if time.time() - start_time > COMPRESSION_TIMEOUT:
                    process.kill()
                    raise TimeoutError(f"压缩操作超时（{COMPRESSION_TIMEOUT}秒）")
                
                # 读取并写入数据
                chunk = input_stream.read(chunk_size)
                if not chunk:
                    break
                
                try:
                    process.stdin.write(chunk)
                    bytes_copied += len(chunk)
                    
                    # 检查进程是否还活着
                    if process.poll() is not None:
                        stderr = process.stderr.read().decode()
                        raise subprocess.CalledProcessError(
                            process.returncode,
                            cmd,
                            f"压缩进程意外退出: {stderr}"
                        )
                except BrokenPipeError:
                    stderr = process.stderr.read().decode()
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        cmd,
                        f"压缩进程管道断开: {stderr}"
                    )
            
            # 关闭输入流并等待进程完成
            process.stdin.close()
            try:
                process.wait(timeout=30)  # 给进程30秒完成压缩
            except subprocess.TimeoutExpired:
                process.kill()
                raise TimeoutError("压缩进程未能在30秒内完成")
            
            if process.returncode != 0:
                stderr = process.stderr.read().decode()
                raise subprocess.CalledProcessError(
                    process.returncode,
                    cmd,
                    f"压缩失败: {stderr}"
                )
        
        # 压缩成功，重命名临时文件
        os.rename(temp_output, output_path)
        
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_output):
            try:
                os.unlink(temp_output)
            except:
                pass
        raise e

if __name__ == "__main__":
    # 使用环境变量中的主机和端口
    logger.info(f"启动服务 - 主机: {API_HOST}, 端口: {API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT) 