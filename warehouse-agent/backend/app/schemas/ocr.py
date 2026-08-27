"""OCR 相关 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional


class OCRRecognizeRequest(BaseModel):
    image_base64: Optional[str] = None