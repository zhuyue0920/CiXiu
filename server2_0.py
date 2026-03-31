from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import json
import io
import requests
import logging
import sys
from datetime import datetime
import os
import gc
from threading import Lock
import base64
from flask_session import Session
import uuid
import shutil
from volcenginesdkarkruntime import Ark  # 替换为Ark客户端

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='', static_folder='.')

# 配置CORS，允许跨域请求
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# 配置Flask会话
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400
Session(app)

# 确保会话存储目录存在
if not os.path.exists('flask_session'):
    os.makedirs('flask_session')

# ========== 调整文件夹结构：按用户隔离uploads和downloads ==========
BASE_UPLOAD_FOLDER = 'uploads'
BASE_DOWNLOAD_FOLDER = 'download'  # 统一下载目录，按用户隔离


def get_user_upload_folder():
    """获取当前用户的上传文件夹（按user_id隔离）"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_folder = os.path.join(BASE_UPLOAD_FOLDER, session['user_id'])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


def get_user_download_folder():
    """获取当前用户的下载文件夹（按user_id隔离）"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_folder = os.path.join(BASE_DOWNLOAD_FOLDER, session['user_id'])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


# 定期清理过期的用户文件夹（同时清理uploads和download）
def cleanup_old_folders():
    try:
        current_time = datetime.now()
        # 清理uploads
        if os.path.exists(BASE_UPLOAD_FOLDER):
            for user_folder in os.listdir(BASE_UPLOAD_FOLDER):
                folder_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder)
                if os.path.isdir(folder_path):
                    modified_time = datetime.fromtimestamp(os.path.getmtime(folder_path))
                    if (current_time - modified_time).total_seconds() > 86400:
                        shutil.rmtree(folder_path)
        # 清理download
        if os.path.exists(BASE_DOWNLOAD_FOLDER):
            for user_folder in os.listdir(BASE_DOWNLOAD_FOLDER):
                folder_path = os.path.join(BASE_DOWNLOAD_FOLDER, user_folder)
                if os.path.isdir(folder_path):
                    modified_time = datetime.fromtimestamp(os.path.getmtime(folder_path))
                    if (current_time - modified_time).total_seconds() > 86400:
                        shutil.rmtree(folder_path)
    except Exception as e:
        logger.error(f"清理过期文件夹时出错: {str(e)}")


# ========== 保留基础路由（会话、文件访问等） ==========
@app.route('/check-session', methods=['GET'])
def check_session():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return jsonify({
        "user_id": session['user_id'],
        "session_active": True
    })


@app.route('/user-images', methods=['GET'])
def get_user_images():
    """返回用户上传的图片列表（兼容原有前端逻辑）"""
    user_upload_folder = get_user_upload_folder()
    user_download_folder = get_user_download_folder()
    images = []

    # 读取上传的原图
    if os.path.exists(user_upload_folder):
        for filename in os.listdir(user_upload_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                image_url = f"/uploads/{session['user_id']}/{filename}"
                images.append({
                    "type": "uploaded",
                    "url": image_url,
                    "filename": filename,
                    "created": datetime.fromtimestamp(
                        os.path.getctime(os.path.join(user_upload_folder, filename))).isoformat()
                })

    # 读取生成的图片
    if os.path.exists(user_download_folder):
        for filename in os.listdir(user_download_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                image_url = f"/download/{session['user_id']}/{filename}"
                images.append({
                    "type": "generated",
                    "url": image_url,
                    "filename": filename,
                    "created": datetime.fromtimestamp(
                        os.path.getctime(os.path.join(user_download_folder, filename))).isoformat()
                })

    return jsonify({"images": images})


@app.after_request
def after_request(response):
    """响应头中间件（保留）"""
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# 错误处理（保留）
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "文件太大"}), 413


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "未找到请求的资源"}), 404


# 允许的文件扩展名（保留）
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 基础路由（保留）
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('.', 'favicon.ico')


# 文件访问路由（新增download路由，适配用户隔离）
@app.route('/uploads/<user_id>/<filename>')
def uploaded_file(user_id, filename):
    return send_from_directory(os.path.join(BASE_UPLOAD_FOLDER, user_id), filename)


@app.route('/download/<user_id>/<filename>')
def downloaded_file(user_id, filename):
    return send_from_directory(os.path.join(BASE_DOWNLOAD_FOLDER, user_id), filename)


# ========== 核心配置：Ark客户端 + 工具函数 ==========
# API Key（替换为你的实际Key）
API_KEY = "7ea23341-a3b0-4c9a-be77-aec9be17cfb1"

# 初始化Ark客户端（全局单例）
ark_client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=API_KEY,
)


# 图片转Base64函数（适配用户文件夹）
def local_image_to_base64(image_path):
    """将本地图片转换为Ark接口支持的Base64编码"""
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"本地图片不存在：{image_path}")

        with open(image_path, "rb") as image_file:
            image_ext = os.path.splitext(image_path)[1].lower()
            mime_type = f"image/{image_ext[1:]}" if image_ext in [".jpg", ".jpeg", ".png"] else "image/jpeg"
            base64_data = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        logger.error(f"转换本地图片为Base64失败：{e}")
        raise


# 下载图片到用户专属download文件夹
def download_image_to_user_download(image_url, save_dir=None, file_name=None):
    """下载图片到当前用户的download文件夹"""
    try:
        # 默认使用用户专属download文件夹
        if not save_dir:
            save_dir = get_user_download_folder()
        os.makedirs(save_dir, exist_ok=True)

        # 生成唯一文件名
        if not file_name:
            file_name = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"

        save_path = os.path.join(save_dir, file_name)

        # 分块下载图片
        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        logger.info(f"图片下载成功！保存路径：{os.path.abspath(save_path)}")
        return save_path
    except Exception as e:
        logger.error(f"图片下载失败：{e}")
        raise


# ========== 核心路由：替换为Ark图片生成逻辑 ==========
@app.route('/generate-image', methods=['POST', 'OPTIONS'])
def generate_image():
    """
    核心功能：上传两张图片 → 调用Ark接口生成融合刺绣图 → 下载到用户download文件夹
    接收参数：
    - image1: 第一张图片（对应原school.jpg）
    - image2: 第二张图片（对应原人物抠出.jpeg）
    - prompt: 自定义提示词（可选，默认使用指定的刺绣融合提示词）
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        user_upload_folder = get_user_upload_folder()
        gc.collect()

        # 1. 获取前端参数
        custom_prompt = request.form.get('prompt', '').strip()
        logger.info(f"收到图片生成请求，用户ID: {session['user_id']}, 自定义提示词: {custom_prompt}")

        # 2. 接收并保存两张上传的图片
        image1_file = request.files.get('image1')
        image2_file = request.files.get('image2')
        if not image1_file or not image2_file:
            return jsonify({"error": "请上传两张图片（image1和image2）"}), 400

        # 保存第一张图片
        image1_filename = None
        image2_filename = None
        image1_path = None
        image2_path = None

        # 处理第一张图片
        if image1_file and allowed_file(image1_file.filename):
            image1_filename = f"image1_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{os.path.splitext(image1_file.filename)[1]}"
            image1_path = os.path.join(user_upload_folder, image1_filename)
            with open(image1_path, 'wb') as f:
                f.write(image1_file.read())
            logger.info(f"第一张图片保存成功: {image1_path}")
        else:
            return jsonify({"error": f"不支持的文件类型: {image1_file.filename if image1_file else '空'}"})

        # 处理第二张图片
        if image2_file and allowed_file(image2_file.filename):
            image2_filename = f"image2_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{os.path.splitext(image2_file.filename)[1]}"
            image2_path = os.path.join(user_upload_folder, image2_filename)
            with open(image2_path, 'wb') as f:
                f.write(image2_file.read())
            logger.info(f"第二张图片保存成功: {image2_path}")
        else:
            return jsonify({"error": f"不支持的文件类型: {image2_file.filename if image2_file else '空'}"})

        # 3. 转换两张图片为Base64
        base64_image1 = local_image_to_base64(image1_path)
        base64_image2 = local_image_to_base64(image2_path)
        base64_image_list = [base64_image1, base64_image2]

        # 4. 构建提示词（默认使用指定的刺绣融合提示词）
        if not custom_prompt:
            custom_prompt = "将图2的人物先缩小一点再放到图1中左侧路灯底下，不要新增路灯，使用图片中的路灯，并将最后的图片转换为刺绣样式"
        logger.info(f"最终使用提示词: {custom_prompt}")

        # 5. 调用Ark接口生成图片
        try:
            imagesResponse = ark_client.images.generate(
                model="doubao-seedream-4-5-251128",
                prompt=custom_prompt,
                image=base64_image_list,
                sequential_image_generation="disabled",
                response_format="url",
                size="2K",
                stream=False,
                watermark=True
            )
            logger.info(f"Ark接口调用成功，响应: {imagesResponse}")
        except Exception as api_error:
            logger.error(f"Ark API调用失败: {str(api_error)}")
            return jsonify({"error": f"API调用失败: {str(api_error)}"}), 500

        # 6. 提取生成的图片URL并下载
        if not hasattr(imagesResponse, 'data') or len(imagesResponse.data) == 0:
            return jsonify({"error": "未生成图片，API返回空数据"}), 500

        generated_image_url = imagesResponse.data[0].url
        # 下载到用户专属download文件夹
        save_path = download_image_to_user_download(generated_image_url)
        # 构造前端可访问的URL
        result_filename = os.path.basename(save_path)
        result_url = f"{request.host_url.rstrip('/')}/download/{session['user_id']}/{result_filename}"

        gc.collect()

        # 7. 返回结果
        return jsonify({
            "success": True,
            "image_url": result_url,
            "original_api_url": generated_image_url,
            "save_path": save_path,
            "message": "图片生成并下载成功（融合两张图+刺绣样式）"
        })

    except Exception as e:
        logger.error(f"处理图片生成请求失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ========== 启动服务 ==========
if __name__ == '__main__':
    logger.info("启动Flask服务器（集成Ark图片生成功能）...")
    from gevent.pywsgi import WSGIServer

    # 限制上传文件大小（16MB）
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    # 启动服务器
    http_server = WSGIServer(('0.0.0.0', 5000), app, log=None)
    logger.info("服务器运行在 http://0.0.0.0:5000")
    http_server.serve_forever()
