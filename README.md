# AI辅助刺绣生成系统使用说明

## 系统简介
本系统是一个基于AI的刺绣图案生成系统，支持多用户同时在线使用。用户可以通过文字描述和上传风格图片来生成独特的刺绣图案。

## 系统要求
- Python 3.8+
- 2GB以上内存
- 10GB以上磁盘空间
- 支持的操作系统：Windows/Linux/MacOS

## 安装步骤

1. 安装Python依赖包：
```bash
pip install flask flask-cors flask-session gevent pillow volcengine
```

2. 配置火山引擎API密钥：
   - 访问[火山引擎官网](https://www.volcengine.com/)
   - 注册账号并创建应用
   - 获取ACCESS_KEY和SECRET_KEY
   - 修改`server.py`中的API配置：
```python
ACCESS_KEY = "您的ACCESS_KEY"
SECRET_KEY = "您的SECRET_KEY"
```

3. 创建必要的目录：
```bash
mkdir -p uploads
mkdir -p flask_session
chmod 755 uploads
chmod 755 flask_session
```

## 启动服务

### Linux/MacOS系统：
1. 给启动脚本添加执行权限：
```bash
chmod +x start_server.sh stop_server.sh
```

2. 启动服务器：
```bash
./start_server.sh
```

3. 停止服务器：
```bash
./stop_server.sh
```

### Windows系统：
1. 直接运行Python脚本：
```bash
python server.py
```

2. 或使用任务管理器关闭Python进程

## 使用说明

1. 访问系统：
   - 打开浏览器访问：`http://服务器IP:5000`
   - 本地访问：`http://localhost:5000`

2. 生成刺绣图案：
   - 在输入框中输入图案描述（建议使用中文）
   - 可选：上传风格参考图片
   - 点击"生成刺绣图片"按钮
   - 等待生成完成

3. 查看历史记录：
   - 系统会自动保存您生成的所有图片
   - 在页面顶部可以看到历史图片列表
   - 点击图片可以放大查看

## 注意事项

1. 图片生成：
   - 描述文字建议使用中文
   - 避免使用敏感词汇
   - 每次生成可能需要30-60秒
   - 建议上传的参考图片大小不超过2MB

2. 数据存储：
   - 用户数据会保存24小时
   - 超过24小时未访问的数据会自动清理
   - 建议及时保存重要的生成结果

3. 系统维护：
   - 定期检查日志文件：`server.log`
   - 定期清理`uploads`目录
   - 确保服务器有足够的存储空间

## 常见问题

1. 无法访问系统：
   - 检查服务器是否正常运行
   - 检查防火墙是否开放5000端口
   - 检查API密钥是否正确配置

2. 图片生成失败：
   - 检查网络连接
   - 确认API密钥是否有效
   - 查看服务器日志获取详细错误信息

3. 上传图片失败：
   - 检查图片格式（支持jpg、png、gif）
   - 确认图片大小不超过限制
   - 检查uploads目录权限