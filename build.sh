#!/bin/bash

echo "🚀 构建前端应用..."
npm run build

echo "📋 拷贝到 backend/static..."
rm -rf backend/static
cp -r build backend/static

echo "✅ 完成！" 