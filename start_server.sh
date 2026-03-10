#!/bin/bash

# 创建必要的目录
mkdir -p uploads
mkdir -p flask_session
chmod 755 uploads
chmod 755 flask_session

# 启动服务器
nohup python server.py > server.log 2>&1 &

echo "服务器已启动，日志文件：server.log" 