import os
import base64
import requests
from volcenginesdkarkruntime import Ark

# API Key
API_KEY = "7ea23341-a3b0-4c9a-be77-aec9be17cfb1"


# 保留：将本地图片转换为 Base64 编码的函数（适配任意本地文件夹，包括 uploads）
def local_image_to_base64(image_path):
    """
    将本地图片文件转换为接口支持的 Base64 编码字符串
    :param image_path: 本地图片的完整路径（这里指向 uploads 文件夹下的图片）
    :return: 带格式前缀的 Base64 编码字符串
    """
    try:
        # 检查图片文件是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"本地图片不存在：{image_path}")

        # 读取图片二进制数据并转换为 Base64
        with open(image_path, "rb") as image_file:
            # 获取图片后缀，确定 MIME 类型（兼容 jpg/jpeg/png）
            image_ext = os.path.splitext(image_path)[1].lower()
            mime_type = f"image/{image_ext[1:]}" if image_ext in [".jpg", ".jpeg", ".png"] else "image/jpeg"
            base64_data = base64.b64encode(image_file.read()).decode("utf-8")

            # 拼接接口要求的 Base64 格式（必须带 data:image/xxx;base64, 前缀）
            return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"转换本地图片为 Base64 失败：{e}")
        raise


# 保留：下载图片到 download 文件夹的核心函数（下载目标不变）
def download_image_to_download(image_url, save_dir="download", file_name=None):
    """
    从图片 URL 下载图片并保存到指定的 download 文件夹
    :param image_url: 生成的图片网络 URL
    :param save_dir: 保存文件夹（默认 download，保持原有下载目标）
    :param file_name: 自定义文件名（不传则自动生成唯一名称，避免覆盖）
    :return: 图片保存的完整路径
    """
    try:
        # 1. 创建 download 文件夹（不存在则创建）
        os.makedirs(save_dir, exist_ok=True)

        # 2. 构造唯一文件名（时间戳，避免覆盖）
        if not file_name:
            import time
            file_name = f"generated_clothes_swap_{int(time.time())}.jpg"

        # 3. 构造跨平台兼容的完整保存路径
        save_path = os.path.join(save_dir, file_name)

        # 4. 分块下载图片
        response = requests.get(image_url, stream=True)
        response.raise_for_status()

        # 5. 二进制写入保存图片
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        print(f"图片下载成功！保存路径：{os.path.abspath(save_path)}")
        return save_path
    except Exception as e:
        print(f"图片下载失败：{e}")
        raise


# 初始化客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=API_KEY,
)

try:
    # 核心修改：定义 uploads 文件夹下的两张本地图片（请替换为你的实际图片文件名）
    image_file_name1 = "school.jpg"  # 第一张图文件名
    image_file_name2 = "人物抠出.jpeg"  # 第二张图文件名

    # 构造完整图片路径（指向 uploads 文件夹，替换原来的 download，兼容跨平台路径）
    image_path1 = os.path.join("uploads", image_file_name1)
    image_path2 = os.path.join("uploads", image_file_name2)

    # 将两张本地图片转换为 Base64 编码，存入列表（来源为 uploads 文件夹）
    base64_image_list = [
        local_image_to_base64(image_path1),
        local_image_to_base64(image_path2)
    ]

    # 调用图片生成接口（image 参数传入 uploads 文件夹图片的 Base64 列表）
    imagesResponse = client.images.generate(
        model="doubao-seedream-4-5-251128",
        prompt="将图2的人物先缩小一点再放到图1中左侧路灯底下，不要新增路灯，使用图片中的路灯，并将最后的图片转换为刺绣样式",
        image=base64_image_list,
        sequential_image_generation="disabled",
        response_format="url",
        size="2K",
        stream=False,
        watermark=True
    )

    # 提取 URL 并下载到 download 文件夹
    generated_image_url = imagesResponse.data[0].url
    download_image_to_download(generated_image_url)

except Exception as e:
    print(f"接口调用失败：{e}")
