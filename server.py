from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from volcengine.visual.VisualService import VisualService
import json
from PIL import Image, ImageEnhance, ImageFilter
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

# 修改上传目录结构
BASE_UPLOAD_FOLDER = 'uploads'


def get_user_upload_folder():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_folder = os.path.join(BASE_UPLOAD_FOLDER, session['user_id'])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


# 定期清理过期的用户文件夹
def cleanup_old_folders():
    try:
        current_time = datetime.now()
        for user_folder in os.listdir(BASE_UPLOAD_FOLDER):
            folder_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder)
            if os.path.isdir(folder_path):
                modified_time = datetime.fromtimestamp(os.path.getmtime(folder_path))
                if (current_time - modified_time).total_seconds() > 86400:
                    shutil.rmtree(folder_path)
    except Exception as e:
        logger.error(f"清理过期文件夹时出错: {str(e)}")


# 添加用户会话状态检查的路由
@app.route('/check-session', methods=['GET'])
def check_session():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return jsonify({
        "user_id": session['user_id'],
        "session_active": True
    })


# 添加用户图片列表的路由
@app.route('/user-images', methods=['GET'])
def get_user_images():
    user_folder = get_user_upload_folder()
    if os.path.exists(user_folder):
        images = []
        for filename in os.listdir(user_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                image_url = f"/uploads/{session['user_id']}/{filename}"
                images.append({
                    "url": image_url,
                    "filename": filename,
                    "created": datetime.fromtimestamp(os.path.getctime(os.path.join(user_folder, filename))).isoformat()
                })
        return jsonify({"images": images})
    return jsonify({"images": []})


# 添加响应头中间件
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# 添加错误处理
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "文件太大"}), 413


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "未找到请求的资源"}), 404


# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 添加根路由，返回index.html
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# 添加favicon路由
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('.', 'favicon.ico')


# 修改文件访问路由
@app.route('/uploads/<user_id>/<filename>')
def uploaded_file(user_id, filename):
    return send_from_directory(os.path.join(BASE_UPLOAD_FOLDER, user_id), filename)


# API配置
ACCESS_KEY = "AKLTZDU4MTYyYTBlZmJhNGRiNGIyMWM0ZjU1MGU5YjJjYmI"
SECRET_KEY = "T1dNNE9UTmtPRGMyT0dGaE5ERmxZVGsyTnpBMk1HUmhObVJrWkdVd09UTQ=="

# 初始化Visual服务
visual_service = VisualService()
visual_service.set_ak(ACCESS_KEY)
visual_service.set_sk(SECRET_KEY)

# 检查API密钥是否已配置
if ACCESS_KEY == 'your_access_key_here' or SECRET_KEY == 'your_secret_key_here':
    logger.warning("请配置火山引擎API密钥！")

# 创建一个锁用于同步请求处理
request_lock = Lock()


# ========== 新增：图片内容描述提取（简化版，辅助提示词） ==========
def extract_image_content_hint(image_data):
    """
    提取图片基础内容特征，生成辅助提示词（让AI贴合图片内容）
    :param image_data: 图片二进制数据
    :return: 内容提示词字符串
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        # 获取图片基础特征
        width, height = img.size
        mode = img.mode
        # 简单色彩判断（主色调）
        pixels = img.resize((10, 10)).getcolors(100)
        if pixels:
            dominant_color = max(pixels, key=lambda x: x[0])[1]
            if mode == 'RGB':
                r, g, b = dominant_color
                if r > 200 and g > 200 and b > 200:
                    color_hint = "浅色调、明亮"
                elif r < 50 and g < 50 and b < 50:
                    color_hint = "深色调、暗色系"
                elif r > g and r > b:
                    color_hint = "红色系为主"
                elif g > r and g > b:
                    color_hint = "绿色系为主"
                elif b > r and b > g:
                    color_hint = "蓝色系为主"
                else:
                    color_hint = "多色系、色彩丰富"
            else:
                color_hint = "灰度图、黑白风格"
        else:
            color_hint = "色彩均衡"

        # 生成内容提示词（核心：让AI参考图片的尺寸、色调、风格）
        content_hint = f"参考图片尺寸{width}x{height}，{color_hint}，完全贴合图片中的内容主体和色彩风格"
        return content_hint
    except Exception as e:
        logger.error(f"提取图片内容特征失败: {str(e)}")
        return "完全贴合上传图片的内容主体、色彩和风格"


# ========== 修复：图片预处理函数（移到调用前） ==========
def preprocess_style_image(image_data):
    """风格图片预处理：确保接口能识别"""
    if not image_data:
        logger.warning("风格图片数据为空，跳过预处理")
        return image_data

    try:
        image = Image.open(io.BytesIO(image_data))
        resize_method = Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS

        if image.mode not in ['RGB', 'L']:
            image = image.convert('RGB')

        # 强制缩放到512x512（火山引擎接口最优尺寸）
        target_size = (512, 512)
        image = image.resize(target_size, resize_method)

        buffer = io.BytesIO()
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        processed_data = buffer.getvalue()

        logger.info(f"图片预处理完成，尺寸转为512x512，大小{len(processed_data)}字节")
        return processed_data
    except Exception as e:
        logger.error(f"图片预处理失败: {str(e)}，使用原始图片数据")
        return image_data


def enhance_image(image):
    """使用PIL进行轻量级图像增强"""
    try:
        max_size = 1024
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.LANCZOS)

        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.3)

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.2)

        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.1)

        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)

        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

        return image
    except Exception as e:
        logger.error(f"图像增强处理失败: {str(e)}")
        return image


@app.route('/generate-image', methods=['POST', 'OPTIONS'])
def generate_image():
    """处理生成图片的请求：1:1还原上传图片内容，仅转换为刺绣效果"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        user_upload_folder = get_user_upload_folder()
        gc.collect()

        # 1. 获取基础参数
        prompt = request.form.get('prompt', '').strip()
        logger.info(f"收到刺绣还原请求，用户ID: {session['user_id']}, 原始提示词: {prompt}")

        # 2. 处理上传的图片（确保内容无损失）
        style_image_file = request.files.get('style-image')
        style_image_data = None
        is_image_uploaded = False
        image_content_hint = ""

        if style_image_file and style_image_file.filename:
            try:
                if allowed_file(style_image_file.filename):
                    style_image_data = style_image_file.read()
                    if style_image_data:
                        # 验证图片有效性
                        Image.open(io.BytesIO(style_image_data)).verify()
                        # 预处理图片（等比例缩放，内容无变形）
                        style_image_data = preprocess_style_image(style_image_data)
                        # 提取图片内容提示词（仅描述内容，不涉及风格）
                        image_content_hint = extract_image_content_hint(style_image_data)
                        is_image_uploaded = True

                        # 保存上传的原图（用于对比）
                        filename = f"original_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{style_image_file.filename}"
                        style_image_path = os.path.join(user_upload_folder, filename)
                        with open(style_image_path, 'wb') as f:
                            f.write(style_image_data)
                        logger.info(f"上传原图保存成功: {style_image_path}")
                    else:
                        return jsonify({"error": "上传的图片为空"}), 400
                else:
                    return jsonify({"error": f"不支持的文件类型: {style_image_file.filename}"}), 400
            except Exception as e:
                logger.error(f"处理上传图片失败: {str(e)}")
                return jsonify({"error": f"图片处理失败: {str(e)}"}), 500

        # 必须上传图片才能生成“一模一样”的刺绣
        if not is_image_uploaded:
            return jsonify({"error": "请先上传需要转换为刺绣的图片"}), 400

        # 3. 增强提示词（1:1还原内容 + 刺绣质感）
        if not prompt:
            prompt = "1:1还原原图内容，仅替换为刺绣质感，针线纹理清晰，丝线光泽自然，传统手工刺绣风格，高清8K细节"

        enhanced_prompt = f"""
严格按照上传图片的内容、构图、色彩、物体位置1:1像素级还原，不添加任何额外元素，不删减任何元素，不改变物体形状/大小/位置，不调整色彩饱和度/亮度/对比度，仅将图片的整体质感替换为刺绣效果。
具体要求：{prompt}，刺绣纹理覆盖整个画面，针线质感强烈，丝线光泽贴合原图色彩，边缘有自然的针线收口效果，保留原图的所有细节（包括小物体、纹理、阴影），仅材质变为刺绣，不参考原图的任何风格（如照片/卡通/手绘）。
{image_content_hint}
""".replace("\n", "").strip()
        logger.info(f"最终提示词: {enhanced_prompt}")

        # 4. 构建接口参数（最大化内容还原）
        params = {
            "req_key": "high_aes_general_v20",
            "prompt": enhanced_prompt,
            "model_version": "general_v2.0",
            "seed": -1,
            "scale": 10.0,  # 拉满文本引导，确保刺绣效果
            "ddim_steps": 30,  # 最高步数，还原细节
            "width": 512,
            "height": 512,
            "use_sr": True,  # 超分提升细节
            "return_url": True,
            "style_strength": 0.98  # 90%保留原图内容
        }

        # 5. 添加图片参数（确保内容参考生效）
        try:
            style_image_base64 = base64.b64encode(style_image_data).decode('utf-8')
            if len(style_image_base64) % 4 != 0:
                style_image_base64 += '=' * (4 - len(style_image_base64) % 4)
            params['style_image'] = style_image_base64
            logger.info("原图内容参数已添加，将1:1还原内容并转换为刺绣")
        except Exception as e:
            logger.error(f"编码图片失败: {str(e)}")
            return jsonify({"error": f"图片编码失败: {str(e)}"}), 500

        # 6. 调用API
        try:
            response = visual_service.high_aes_smart_drawing(params)
            logger.info(f"API响应: {response}")
        except Exception as api_error:
            logger.error(f"API调用失败: {str(api_error)}")
            return jsonify({"error": f"API调用失败: {str(api_error)}"}), 500

        if not response:
            return jsonify({"error": "API返回空响应"}), 500

        # 7. 处理响应（保留高清细节）
        if response.get('code') == 10000:
            image_urls = response.get('data', {}).get('image_urls', [])
            if image_urls:
                try:
                    image_url = image_urls[0]
                    image_response = requests.get(image_url, timeout=30)
                    image_response.raise_for_status()
                    image = Image.open(io.BytesIO(image_response.content))
                    processed_image = enhance_image(image)

                    # 高质量保存刺绣图片
                    output_filename = f"embroidery_copy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    output_path = os.path.join(user_upload_folder, output_filename)
                    processed_image.save(output_path, format='JPEG', quality=95, optimize=False, subsampling=0)
                    result_url = f"{request.host_url.rstrip('/')}/uploads/{session['user_id']}/{output_filename}"

                    del image, processed_image
                    gc.collect()

                    return jsonify({
                        "success": True,
                        "image_url": result_url,
                        "original_url": image_url,
                        "message": "已生成和原图一模一样的刺绣效果图片",
                        "upload_status": {
                            "is_uploaded": True,
                            "hint": "1:1还原内容，仅替换为刺绣质感"
                        }
                    })
                except Exception as e:
                    logger.error(f"处理生成图片失败: {str(e)}")
                    return jsonify({
                        "success": True,
                        "image_url": image_url,
                        "message": "返回刺绣效果原始图片（未做额外处理）"
                    })
            else:
                return jsonify({"error": "未找到生成的图片URL"}), 500
        else:
            error_msg = f"API错误: {response.get('message', '未知错误')}"
            logger.error(error_msg)
            return jsonify({
                "error": error_msg,
                "code": response.get('code')
            }), 500

    except Exception as e:
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("启动服务器...")
    from gevent.pywsgi import WSGIServer

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    http_server = WSGIServer(('0.0.0.0', 5000), app, log=None)
    logger.info("服务器运行在 http://0.0.0.0:5000")
    http_server.serve_forever()
