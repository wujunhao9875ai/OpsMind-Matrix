"""OCR 服务 — PaddleOCR HTTP 调用 + 结构化提取"""
import re
import httpx
from typing import Optional
from app.config import settings


# 铭牌关键字段提取规则
EXTRACTION_PATTERNS = {
    "serial_number": [
        r"S\/?N[:\s]*([A-Za-z0-9\-]+)",
        r"Serial\s*No[.:\s]*([A-Za-z0-9\-]+)",
        r"序列号[：:\s]*([A-Za-z0-9\-]+)",
        r"SN[：:\s]*([A-Za-z0-9\-]+)",
    ],
    "model": [
        r"Model[:\s]*([A-Za-z0-9\-\s]+)",
        r"型号[：:\s]*([A-Za-z0-9\-\s]+)",
        r"MODEL[:\s]*([A-Za-z0-9\-\s]+)",
    ],
    "manufacture_date": [
        r"MFG[:\s]*(\d{4}[-/]\d{2})",
        r"生产日期[：:\s]*(\d{4}[-/]\d{2})",
        r"Date[:\s]*(\d{4}[-/]\d{2})",
    ],
    "brand": [
        r"(HP|Canon|EPSON|Brother|Lenovo|Dell|Samsung|Xerox|Fujitsu|华为|联想|佳能|惠普|爱普生|兄弟)",
    ],
}


def extract_structured(raw_text: str, confidence: float) -> dict:
    """从 OCR 原始文本中提取结构化字段"""
    extracted = {}
    for field, patterns in EXTRACTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                extracted[field] = match.group(1).strip()
                break

    # 生成建议
    suggestions = {}
    if extracted.get("brand") and extracted.get("model"):
        suggestions["name"] = f"{extracted['brand']} {extracted['model']}"
        suggestions["category"] = _guess_category(extracted.get("brand", ""), extracted.get("model", ""))

    return {
        "raw_text": raw_text,
        "extracted": extracted,
        "confidence": confidence,
        "suggestions": suggestions if suggestions else None,
    }


def _guess_category(brand: str, model: str) -> str:
    """根据品牌和型号推测设备类别"""
    brand_lower = brand.lower()
    model_lower = model.lower()
    if any(kw in model_lower for kw in ["printer", "laserjet", "inkjet", "打印机", "打印"]):
        return "printer"
    if any(kw in brand_lower for kw in ["hp", "canon", "epson", "brother", "xerox", "惠普", "佳能", "爱普生"]):
        return "printer"
    if any(kw in model_lower for kw in ["switch", "router", "交换机", "路由器"]):
        return "network"
    if any(kw in model_lower for kw in ["server", "服务器", "proliant", "poweredge"]):
        return "server"
    if any(kw in model_lower for kw in ["monitor", "display", "显示器"]):
        return "monitor"
    return "other"


def recognize_nameplate(image_bytes: bytes) -> dict:
    """调用 PaddleOCR 服务识别设备铭牌"""
    ocr_url = getattr(settings, "paddleocr_url", "http://paddleocr:8866")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{ocr_url}/ocr/recognize",
                files={"image": ("nameplate.jpg", image_bytes, "image/jpeg")},
            )
            if response.status_code == 200:
                data = response.json()
                raw_text = " ".join([item.get("text", "") for item in data.get("results", [])])
                confidence = data.get("confidence", 0.0)
                return extract_structured(raw_text, confidence)
            else:
                return {"raw_text": "", "extracted": {}, "confidence": 0.0, "error": f"OCR 服务返回错误: {response.status_code}"}
    except httpx.ConnectError:
        return {"raw_text": "", "extracted": {}, "confidence": 0.0, "error": "OCR 服务暂时不可用，请稍后重试或手动录入"}
    except Exception as e:
        return {"raw_text": "", "extracted": {}, "confidence": 0.0, "error": f"OCR 识别失败: {str(e)}"}