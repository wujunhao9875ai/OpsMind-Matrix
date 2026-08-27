"""OCR 铭牌识别 API"""
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.core.ocr_service import recognize_nameplate
from app.schemas.warehouse import OCRRecognizeResponse

router = APIRouter(prefix="/api/v1/warehouse/ocr", tags=["ocr"])


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/recognize", response_model=OCRRecognizeResponse)
async def ocr_recognize(
    image: UploadFile = File(...),
):
    """上传设备铭牌图片，返回 OCR 识别结果"""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="图片过大，请压缩后重试（最大 10MB）")

    result = recognize_nameplate(image_bytes)

    if result.get("error"):
        if "OCR 服务暂时不可用" in result["error"]:
            raise HTTPException(status_code=503, detail=result["error"])
        raise HTTPException(status_code=500, detail=result["error"])

    return OCRRecognizeResponse(
        raw_text=result["raw_text"],
        extracted=result["extracted"],
        confidence=result["confidence"],
        suggestions=result.get("suggestions"),
    )