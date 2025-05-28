import React, { useState, useEffect } from 'react';
import axios from 'axios';

// 使用环境变量或默认值，单端口模式下使用相对路径
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';
// 从环境变量获取密码
const AUTH_PASSWORD = process.env.REACT_APP_AUTH_PASSWORD || 'admin123';

interface DownloadedFile {
  name: string;
  size: number;
  created_at: string;
  path: string;
}

function App() {
  const [imageName, setImageName] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [detail, setDetail] = useState('');
  const [output, setOutput] = useState<string[]>([]);
  const [downloadedFiles, setDownloadedFiles] = useState<DownloadedFile[]>([]);
  const [isClearing, setIsClearing] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showOutput, setShowOutput] = useState(false);

  // 组件加载时检查是否已经认证过（从localStorage读取）
  useEffect(() => {
    const authenticated = localStorage.getItem('docker-pull-authenticated');
    if (authenticated === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  // 处理认证
  const handleAuthenticate = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === AUTH_PASSWORD) {
      setIsAuthenticated(true);
      setError('');
      // 存储认证状态到localStorage
      localStorage.setItem('docker-pull-authenticated', 'true');
    } else {
      setError('密码错误，请重试');
    }
  };

  // 获取已下载文件列表
  const fetchDownloadedFiles = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/downloaded-files`);
      setDownloadedFiles(response.data);
    } catch (error) {
      console.error('获取文件列表失败:', error);
    }
  };

  // 组件加载时获取文件列表
  useEffect(() => {
    if (isAuthenticated) {
      fetchDownloadedFiles();
    }
  }, [isAuthenticated]);

  // 检查下载进度
  const checkProgress = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/pull-progress?image_name=${imageName}`);
      const { status, progress, detail, output } = response.data;
      setStatus(status);
      setProgress(progress);
      setDetail(detail);
      setOutput(output);
      
      // 如果状态是 complete 或 error，停止轮询
      if (status === 'complete' || status === 'error') {
        setLoading(false);
      }
    } catch (error) {
      console.error('获取进度失败:', error);
      setStatus('error');
      setLoading(false);
    }
  };

  // 处理表单提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus('starting');
    setProgress(0);
    setDetail('');
    setOutput([]);
    setShowOutput(false);

    let progressInterval: NodeJS.Timeout | null = null;

    try {
      // 先启动下载进程
      console.log('开始下载镜像:', imageName);
      await axios.post(`${API_BASE_URL}/pull-image`, {
        image_name: imageName
      });

      // 立即获取一次进度
      try {
        const response = await axios.get(`${API_BASE_URL}/pull-progress?image_name=${imageName}`);
        const { status, progress, detail, output } = response.data;
        console.log('初始进度:', { status, progress, detail, output });
        setStatus(status);
        setProgress(progress);
        setDetail(detail);
        setOutput(output || []);
      } catch (error) {
        console.error('获取初始进度失败:', error);
      }

      // 开始更频繁的轮询进度（每500毫秒）
      progressInterval = setInterval(async () => {
        try {
          const response = await axios.get(`${API_BASE_URL}/pull-progress?image_name=${imageName}`);
          const { status, progress, detail, output } = response.data;
          console.log('轮询进度:', { status, progress, detail, outputLength: output?.length });
          
          setStatus(status);
          setProgress(progress);
          setDetail(detail);
          setOutput(output || []);
          
          // 如果状态是 complete 或 error，停止轮询
          if (status === 'complete' || status === 'error') {
            console.log('下载完成，停止轮询');
            if (progressInterval) {
              clearInterval(progressInterval);
              progressInterval = null;
            }
            if (status === 'complete') {
              setLoading(false);
              // 下载完成后刷新文件列表
              fetchDownloadedFiles();
            } else {
              setLoading(false);
            }
          }
        } catch (error) {
          console.error('获取进度失败:', error);
          if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
          }
          setStatus('error');
          setLoading(false);
        }
      }, 500); // 改为每500毫秒轮询一次

    } catch (error) {
      console.error('下载失败:', error);
      setStatus('error');
      setLoading(false);
      if (progressInterval) {
        clearInterval(progressInterval);
      }
    }
  };

  // 下载文件
  const downloadFile = async (path: string, filename: string) => {
    try {
      // 使用 window.open 在新标签页中下载，避免阻塞主页面
      window.open(`${API_BASE_URL}/download-file?path=${encodeURIComponent(path)}`, '_blank');
    } catch (error) {
      console.error('下载文件失败:', error);
      alert('下载文件失败，请重试');
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleClearDownloads = async () => {
    if (!window.confirm('确定要清空所有已下载的镜像吗？此操作不可恢复。')) {
      return;
    }

    try {
      setIsClearing(true);
      await axios.delete(`${API_BASE_URL}/clear-downloads`);
      setDownloadedFiles([]);
      alert('所有镜像已清空');
    } catch (error) {
      console.error('清空镜像失败:', error);
      alert('清空镜像失败，请查看控制台了解详情');
    } finally {
      setIsClearing(false);
    }
  };

  // 登出方法
  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('docker-pull-authenticated');
  };

  // 如果未认证，显示认证页面
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
        <div className="relative py-3 mx-auto max-w-2xl">
          <div className="relative px-4 py-10 bg-white shadow-lg rounded-3xl">
            <div className="mx-auto" style={{ width: '400px', maxWidth: '100%' }}>
              <div className="divide-y divide-gray-200">
                <div className="py-8 text-base leading-6 space-y-3 text-gray-700 sm:text-lg sm:leading-7">
                  <h1 className="text-xl font-bold text-center mb-8">Docker镜像下载器</h1>
                  
                  <form onSubmit={handleAuthenticate} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">请输入访问密码</label>
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="输入密码"
                        className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                      />
                      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
                    </div>
                    <button
                      type="submit"
                      className="w-full bg-blue-500 text-white py-1.5 px-4 text-sm rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    >
                      登录
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 mx-auto max-w-4xl">
        <div className="relative px-4 py-10 bg-white shadow-lg rounded-3xl">
          <div className="w-full mx-auto">
            <div className="divide-y divide-gray-200">
              <div className="py-8 text-base leading-6 space-y-3 text-gray-700 sm:text-lg sm:leading-7">
                <div className="flex justify-between items-center mb-4">
                  <h1 className="text-xl font-bold">Docker镜像下载器</h1>
                  <button
                    onClick={handleLogout}
                    className="px-3 py-1 text-sm font-medium text-gray-500 hover:text-gray-700"
                  >
                    退出登录
                  </button>
                </div>
                
                {/* 下载表单 - 固定800px宽度 */}
                <div className="mx-auto space-y-3" style={{ width: '800px', maxWidth: '100%' }}>
                  <form onSubmit={handleSubmit} className="space-y-3">
                    <div>
                      <input
                        type="text"
                        value={imageName}
                        onChange={(e) => setImageName(e.target.value)}
                        placeholder="输入镜像名称 (例如: nginx:latest)"
                        className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full bg-blue-500 text-white py-1.5 px-4 text-sm rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
                    >
                      {loading ? '下载中...' : '下载'}
                    </button>
                  </form>

                  {/* 进度条和状态信息 */}
                  {loading && (
                    <div className="mt-3 space-y-2">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-300 ${
                            status === 'error' ? 'bg-red-600' : 'bg-blue-600'
                          }`}
                          style={{ width: `${progress}%` }}
                        ></div>
                      </div>
                      <div className="flex justify-between items-center">
                        <p className="text-sm text-gray-600">
                          {status === 'starting' && '正在开始下载...'}
                          {status === 'downloading' && '正在下载...'}
                          {status === 'saving' && '正在保存镜像...'}
                          {status === 'verifying' && '正在验证...'}
                          {status === 'complete' && '下载完成'}
                          {status === 'error' && '下载出错'}
                          {!['starting', 'downloading', 'saving', 'verifying', 'complete', 'error'].includes(status) && '处理中...'}
                        </p>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs text-gray-500">{progress}%</span>
                          {output.length > 0 && (
                            <button
                              onClick={() => setShowOutput(!showOutput)}
                              className="text-xs text-blue-500 hover:text-blue-700"
                            >
                              {showOutput ? '隐藏详情' : '显示详情'}
                            </button>
                          )}
                        </div>
                      </div>
                      {detail && (
                        <p className="text-xs text-gray-500">{detail}</p>
                      )}
                      {/* 实时日志输出 */}
                      {output.length > 0 && showOutput && (
                        <div className="mt-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-gray-600">实时日志:</span>
                            <button
                              onClick={() => setShowOutput(!showOutput)}
                              className="text-xs text-gray-400 hover:text-gray-600"
                            >
                              收起
                            </button>
                          </div>
                          <div 
                            className="bg-gray-900 text-green-400 p-3 rounded text-xs font-mono overflow-auto max-h-60"
                            style={{ 
                              fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                              lineHeight: '1.4'
                            }}
                          >
                            {output.slice(-50).map((line, index) => (
                              <div 
                                key={index} 
                                className={`mb-1 ${
                                  line.includes('[错误]') ? 'text-red-400' : 
                                  line.includes('完成') ? 'text-blue-400' : 
                                  line.includes('开始') ? 'text-yellow-400' : 
                                  'text-green-400'
                                }`}
                              >
                                {line}
                              </div>
                            ))}
                            {output.length > 50 && (
                              <div className="text-gray-500 text-center py-1">
                                ... 显示最近50条日志 (共{output.length}条) ...
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 已下载文件列表区域 - 也固定800px宽度 */}
                <div className="mx-auto mt-8" style={{ width: '800px', maxWidth: '100%' }}>
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-semibold text-gray-900">已下载的镜像</h2>
                    {downloadedFiles.length > 0 && (
                      <button
                        onClick={handleClearDownloads}
                        disabled={isClearing}
                        className={`px-3 py-1 text-sm font-medium rounded-md ${
                          isClearing
                            ? 'bg-gray-300 cursor-not-allowed'
                            : 'bg-red-600 hover:bg-red-700 text-white'
                        }`}
                      >
                        {isClearing ? '清空中...' : '清空所有'}
                      </button>
                    )}
                  </div>
                  {/* 搜索框 */}
                  <div className="mb-4">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="搜索文件名..."
                      className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div className="bg-white shadow overflow-hidden sm:rounded-md">
                    {downloadedFiles.length > 0 ? (
                      <div className="space-y-3 min-h-[200px]">
                        {downloadedFiles
                          .filter(file => 
                            file.name.toLowerCase().includes(searchQuery.toLowerCase())
                          )
                          .map((file) => (
                          <div
                            key={file.path}
                            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                          >
                            <div className="flex-1 min-w-0 mr-4">
                              <p className="font-medium text-sm truncate">{file.name}</p>
                              <p className="text-xs text-gray-500">
                                {formatFileSize(file.size)} - {file.created_at}
                              </p>
                            </div>
                            <button
                              onClick={() => downloadFile(file.path, file.name)}
                              className="bg-green-500 text-white px-3 py-1 text-sm rounded-md hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 flex-shrink-0"
                            >
                              下载
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-4 text-center text-sm text-gray-500">
                        暂无下载文件
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App; 