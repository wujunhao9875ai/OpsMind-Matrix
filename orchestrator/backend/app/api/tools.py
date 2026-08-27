from fastapi import APIRouter
from app.core.discovery import pools

router = APIRouter(prefix="/api/tools")

@router.get("/marketplace")
async def get_tool_marketplace():
    """Return the tool marketplace (all registered agents and their tools)."""
    return {
        "agents": {
            "ops-agent": {"tools": ["rag_search", "intent_classify", "prefill_ticket", "chat_reply"], "status": "healthy"},
            "dispatch-agent": {"tools": ["create_ticket", "assign_ticket", "query_tickets", "get_engineers", "urge_ticket", "resolve_ticket", "reassign_ticket", "cancel_ticket"], "status": "healthy"},
            "warehouse-agent": {"tools": ["stock_in", "stock_out", "device_query", "ocr_recognize", "spare_request", "inventory_check", "device_status_change", "transfer_device"], "status": "healthy"},
            "data-platform": {"tools": ["export_dataset", "query_analytics", "material_generate", "data_import"], "status": "healthy"},
        }
    }