export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  msg_type: "text" | "image";
  confidence?: number;
  sources?: Array<{ title: string; score: number }>;
  created_at?: string;
}

export interface ChatSession {
  id: string;
  username: string;
  title: string;
  summary: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface WebSocketMessage {
  type: "reply_start" | "reply_chunk" | "reply_end" | "ticket_preview";
  payload: Record<string, unknown>;
}

export interface Ticket {
  id: string;
  ticket_no: string;
  title: string;
  description: string;
  fault_category: string;
  urgency: "low" | "medium" | "high" | "critical";
  device_info?: Record<string, unknown>;
  location?: string;
  status: "created" | "assigned" | "in_progress" | "resolved" | "closed" | "cancelled";
  assigned_to?: string | null;
  assigned_at?: string;
  resolution?: string;
  resolved_at?: string;
  closed_at?: string;
  sla_deadline?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TicketLog {
  id: string;
  action: string;
  operator_id?: string;
  from_status?: string;
  to_status?: string;
  comment?: string;
  extra_data?: Record<string, unknown>;
  created_at?: string;
}

export interface Engineer {
  id: string;
  user_id: string;
  display_name: string;
  skills: string[];
  skill_levels: Record<string, number>;
  status: "available" | "busy" | "offline";
  max_concurrent: number;
  current_load: number;
  total_completed: number;
  avg_resolution_minutes: number;
  rating: number;
}

export interface TicketStats {
  total: number;
  by_status: Record<string, number>;
  by_urgency: Record<string, number>;
}

export interface SlaStats {
  overdue: number;
  unassigned: number;
}

export interface WebSocketNotification {
  type: string;
  payload: Record<string, unknown>;
}

export interface WarehouseOverview {
  total_devices: number;
  total_inventory_types: number;
  low_stock_count: number;
  pending_spare_requests: number;
  damaged_count: number;
  stock_in_this_month: number;
  stock_out_this_month: number;
}

export interface WarehouseLocation {
  id: string;
  name: string;
  code: string;
  address: string | null;
  manager_id: string | null;
  status: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface InventoryItem {
  id: string;
  name: string;
  category: string;
  model_spec: string | null;
  unit: string;
  quantity: number;
  available_quantity: number;
  min_threshold: number;
  max_threshold: number;
  location_id: string | null;
  unit_price: number | null;
  version: number;
  last_restock_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InventoryListResponse {
  total: number;
  page: number;
  page_size: number;
  items: InventoryItem[];
}

export interface DeviceItem {
  id: string;
  device_no: string;
  serial_number: string | null;
  name: string;
  model: string | null;
  category: string;
  brand: string | null;
  status: string;
  location_id: string | null;
  purchase_date: string | null;
  warranty_expiry: string | null;
  purchase_price: number | null;
  supplier: string | null;
  consumable_id: string | null;
  last_ticket_id: string | null;
  version: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceListResponse {
  total: number;
  page: number;
  page_size: number;
  items: DeviceItem[];
}

export interface DeviceLog {
  id: string;
  device_id: string;
  action: string;
  from_status: string | null;
  to_status: string | null;
  operator_id: string | null;
  related_ticket_id: string | null;
  repair_vendor: string | null;
  repair_cost: number | null;
  expected_return_date: string | null;
  comment: string | null;
  created_at: string;
}

export interface InventoryTransaction {
  id: string;
  inventory_id: string;
  transaction_type: string;
  quantity_change: number;
  quantity_before: number;
  quantity_after: number;
  related_ticket_id: string | null;
  operator_id: string | null;
  comment: string | null;
  created_at: string;
}

export interface SparePartRequest {
  id: string;
  ticket_id: string;
  consumable_id: string | null;
  inventory_id: string | null;
  item_name: string;
  quantity: number;
  status: string;
  requested_by: string | null;
  approved_by: string | null;
  fulfilled_at: string | null;
  rejected_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface SparePartRequestListResponse {
  total: number;
  page: number;
  page_size: number;
  items: SparePartRequest[];
}

export const DEVICE_STATUS_LABELS: Record<string, string> = {
  in_stock: "在库",
  allocated: "已分配",
  in_use: "使用中",
  damaged: "已损坏",
  in_repair: "维修中",
  repaired: "已修复",
  scrapped: "已报废",
};

export const DEVICE_STATUS_COLORS: Record<string, string> = {
  in_stock: "success",
  allocated: "warning",
  in_use: "primary",
  damaged: "danger",
  in_repair: "warning",
  repaired: "success",
  scrapped: "info",
};

export const DEVICE_CATEGORY_LABELS: Record<string, string> = {
  printer: "打印机",
  computer: "电脑",
  network: "网络设备",
  server: "服务器",
  monitor: "显示器",
  other: "其他",
};