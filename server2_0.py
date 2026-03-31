from flask import Flask, request, jsonify
from flask_cors import CORS

# 初始化Flask
app = Flask(__name__)
# 允许所有跨域（线上测试专用）
CORS(app)

# 核心接口：直接返回测试图片，跳过AI崩溃逻辑
@app.route('/generate-image', methods=['POST'])
def generate_image():
    # 直接返回测试响应，不调用任何AI包
    return jsonify({
        "success": True,
        "image_url": "https://picsum.photos/512/512"  # 随机测试图片
    })

# Render要求：必须用环境变量PORT，不能写死5000
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
