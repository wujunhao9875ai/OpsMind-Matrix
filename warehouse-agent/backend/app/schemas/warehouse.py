"""库房相关 Pydantic 模型"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date
import uuid


# ---- Warehouse Location ----
class WarehouseLocationCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    description: Optional[str] = None


class WarehouseLocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    description: Optional[str] = None


class WarehouseLocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Device ----
class DeviceCreate(BaseModel):
    serial_number: Optional[str] = None
    name: str
    model: Optional[str] = None
    category: str = "other"
    brand: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    notes: Optional[str] = None


class DeviceStatusChange(BaseModel):
    action: str
    comment: Optional[str] = None
    repair_vendor: Optional[str] = None
    repair_cost: Optional[float] = None
    expected_return_date: Optional[date] = None
    related_ticket_id: Optional[uuid.UUID] = None


class DeviceTransfer(BaseModel):
    to_location_id: uuid.UUID
    comment: Optional[str] = None


class DeviceResponse(BaseModel):
    id: uuid.UUID
    device_no: str
    serial_number: Optional[str] = None
    name: str
    model: Optional[str] = None
    category: str
    brand: Optional[str] = None
    status: str
    location_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    version: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DeviceResponse]


# ---- Device Log ----
class DeviceLogResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    operator_id: Optional[uuid.UUID] = None
    related_ticket_id: Optional[uuid.UUID] = None
    repair_vendor: Optional[str] = None
    repair_cost: Optional[float] = None
    expected_return_date: Optional[date] = None
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Inventory ----
class InventoryCreate(BaseModel):
    name: str
    category: str = "consumable"
    model_spec: Optional[str] = None
    unit: str = "个"
    quantity: int = 0
    min_threshold: int = 5
    max_threshold: int = 100
    location_id: Optional[uuid.UUID] = None
    unit_price: Optional[float] = None


class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    model_spec: Optional[str] = None
    unit: Optional[str] = None
    min_threshold: Optional[int] = None
    max_threshold: Optional[int] = None
    location_id: Optional[uuid.UUID] = None
    unit_price: Optional[float] = None


class StockInRequest(BaseModel):
    quantity: int = Field(gt=0)
    unit_price: Optional[float] = None
    comment: Optional[str] = None


class StockOutRequest(BaseModel):
    quantity: int = Field(gt=0)
    related_ticket_id: Optional[uuid.UUID] = None
    comment: Optional[str] = None


class StockAdjustRequest(BaseModel):
    new_quantity: int = Field(ge=0)
    comment: str


class InventoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    model_spec: Optional[str] = None
    unit: str
    quantity: int
    available_quantity: int
    min_threshold: int
    max_threshold: int
    location_id: Optional[uuid.UUID] = None
    unit_price: Optional[float] = None
    version: int
    last_restock_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[InventoryResponse]


# ---- Inventory Transaction ----
class InventoryTransactionResponse(BaseModel):
    id: uuid.UUID
    inventory_id: uuid.UUID
    transaction_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    related_ticket_id: Optional[uuid.UUID] = None
    related_device_id: Optional[uuid.UUID] = None
    from_location_id: Optional[uuid.UUID] = None
    to_location_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Spare Part Request ----
class SparePartRequestResponse(BaseModel):
    id: uuid.UUID
    ticket_id: str
    inventory_id: Optional[uuid.UUID] = None
    item_name: str
    quantity: int
    status: str
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    fulfilled_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SparePartRequestListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SparePartRequestResponse]


# ---- Warehouse Stats ----
class WarehouseOverviewResponse(BaseModel):
    total_devices: int
    total_inventory_types: int
    low_stock_count: int
    pending_spare_requests: int
    damaged_count: int
    stock_in_this_month: int
    stock_out_this_month: int


# ---- OCR ----
class OCRRecognizeResponse(BaseModel):
    raw_text: str
    extracted: dict
    confidence: float
    suggestions: Optional[dict] = None