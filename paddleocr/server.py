"""
PaddleOCR HTTP 服务 - 兼容 paddlepaddle/paddleocr Docker 镜像的 API
监听 8866 端口，提供 OCR 识别接口
"""
import os
import json
import base64
import tempfile
from flask import Flask, request, jsonify

app = Flask(__name__)

# 延迟加载 OCR 模型（首次请求时加载）
ocr = None


def get_ocr():
    global ocr
    if ocr is None:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
    return ocr


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/predict/ocr_system', methods=['POST'])
@app.route('/ocr', methods=['POST'])
def predict():
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            data = {}

        images = data.get('images', [])
        if not images:
            return jsonify({"error": "no images provided"}), 400

        model = get_ocr()
        results = []

        for img_b64 in images:
            # 解码 base64
            if isinstance(img_b64, str):
                if img_b64.startswith('data:'):
                    img_b64 = img_b64.split(',', 1)[1]
                img_bytes = base64.b64decode(img_b64)
            else:
                img_bytes = img_b64

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(img_bytes)
                tmp_path = f.name

            try:
                result = model.ocr(tmp_path, cls=True)
                results.append(result)
            finally:
                os.unlink(tmp_path)

        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8866, debug=False)