"""跨 Agent 编排引擎"""
from app.core.mcp_client import mcp_client
from app.core.logger import setup_logger, log_event

logger = setup_logger("orchestrator")

async def handle_spare_request(ticket_id: str, item_name: str, quantity: int, trace_id: str = None) -> dict:
    """Handle spare part request: dispatch → warehouse"""
    # Step 1: Check ticket status
    ticket_result = await mcp_client.call_tool("dispatch-agent", "query_tickets", {"ticket_id": ticket_id}, trace_id)
    
    # Step 2: Create spare request in warehouse
    spare_result = await mcp_client.call_tool("warehouse-agent", "spare_request", {
        "item_name": item_name,
        "quantity": quantity,
        "ticket_id": ticket_id,
    }, trace_id)
    
    return {
        "ticket": ticket_result,
        "spare_request": spare_result,
        "message": f"已为工单 {ticket_id} 申请 {item_name} x{quantity}，等待库管员备货"
    }