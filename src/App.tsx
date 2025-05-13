import React, { useState, useEffect } from 'react';
import axios from 'axios';

// 使用环境变量或默认值
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

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
  const [downloadedFiles, setDownloadedFiles] = useState<DownloadedFile[]>([]);
  const [isClearing, setIsClearing] = useState(false);

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
    fetchDownloadedFiles();
  }, []);

  // 检查下载进度
  const checkProgress = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/pull-progress?image_name=${imageName}`);
      const { status, progress } = response.data;
      setStatus(status);
      setProgress(progress);
    } catch (error) {
      console.error('获取进度失败:', error);
    }
  };

  // 下载文件
  const downloadFile = async (path: string, filename: string) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/download-file?path=${encodeURIComponent(path)}`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('下载文件失败:', error);
    }
  };

  // 处理表单提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus('downloading');
    setProgress(0);

    try {
      const response = await axios.post(`${API_BASE_URL}/pull-image`, {
        image_name: imageName
      }, {
        responseType: 'blob'
      });

      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${imageName.replace('/', '_')}.tar`);
      document.body.appendChild(link);
      link.click();
      link.remove();

      setStatus('complete');
      setProgress(100);
      // 刷新文件列表
      fetchDownloadedFiles();
    } catch (error) {
      console.error('下载失败:', error);
      setStatus('error');
    } finally {
      setLoading(false);
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

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-4xl sm:mx-auto">
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-12">
          <div className="max-w-4xl mx-auto">
            <div className="divide-y divide-gray-200">
              <div className="py-8 text-base leading-6 space-y-3 text-gray-700 sm:text-lg sm:leading-7">
                <h1 className="text-xl font-bold text-center mb-8">Docker镜像下载器</h1>
                
                {/* 下载表单 */}
                <div className="max-w-2xl mx-auto space-y-3">
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

                  {/* 进度条 */}
                  {loading && (
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progress}%` }}
                        ></div>
                      </div>
                      <p className="text-xs text-gray-600 mt-1">{status}</p>
                    </div>
                  )}
                </div>

                {/* 已下载文件列表区域 - 始终显示，但内容根据状态变化 */}
                <div className="max-w-2xl mx-auto mt-8">
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
                  <div className="bg-white shadow overflow-hidden sm:rounded-md">
                    {downloadedFiles.length > 0 ? (
                      <div className="space-y-3">
                        {downloadedFiles.map((file) => (
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