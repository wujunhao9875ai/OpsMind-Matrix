from fastapi import APIRouter, HTTPException
from app.schemas.dataset import DatasetExportRequest, DatasetResponse
from app.core.dataset_builder import export_dataset as build_dataset

router = APIRouter(prefix="/api/v1", tags=["export"])


@router.post("/export", response_model=DatasetResponse)
async def export_dataset_api(request: DatasetExportRequest):
    """REST endpoint for dataset export."""
    try:
        result = await build_dataset(
            dataset_type=request.dataset_type,
            format=request.format,
            split=request.split,
            size=request.size,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset export failed: {str(e)}")


@router.get("/exports")
async def list_exports():
    """List recent dataset exports."""
    # In production, query from the datasets table
    return {"exports": [], "total": 0}