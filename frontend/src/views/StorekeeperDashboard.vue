<template>
  <div class="storekeeper-dashboard">
    <el-header class="dashboard-header">
      <h2>库房管理后台</h2>
      <div class="header-right">
        <el-tag type="success" v-if="wsConnected">AI 助手在线</el-tag>
        <el-tag type="info" v-else>AI 助手离线</el-tag>
        <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
      </div>
    </el-header>

    <el-main class="dashboard-main">
      <el-row :gutter="16" class="stats-row">
        <el-col :span="4" v-for="stat in statsCards" :key="stat.label">
          <el-card :body-style="{ padding: '16px' }" shadow="hover" class="stat-card-wrapper" @click="handleStatClick(stat)">
            <div class="stat-card" :class="{ clickable: stat.clickable }">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
              <el-tag v-if="stat.alert" :type="stat.alertType" size="small" effect="dark">{{ stat.alert }}</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="section-card" style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>库房管理 ({{ locations.length }} 个库房)</span>
            <el-button type="primary" size="small" @click="showCreateLocationDialog">新增库房</el-button>
          </div>
        </template>
        <div v-if="locations.length === 0" class="empty-state">暂无库房，请新增</div>
        <el-row v-else :gutter="12">
          <el-col :span="6" v-for="loc in locations" :key="loc.id" style="margin-bottom: 12px">
            <el-card shadow="hover" :body-style="{ padding: '12px' }">
              <div class="location-card">
                <div class="location-name">{{ loc.name }}</div>
                <div class="location-code">{{ loc.code }}</div>
                <div class="location-desc" v-if="loc.description">{{ loc.description }}</div>
                <el-tag :type="loc.status === 'active' ? 'success' : 'info'" size="small">{{ loc.status === 'active' ? '启用' : '停用' }}</el-tag>
                <div class="location-actions">
                  <el-button size="small" text @click="showEditLocationDialog(loc)">编辑</el-button>
                  <el-button size="small" text type="danger" @click="handleDeleteLocation(loc)">删除</el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-card>

      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="14">
          <el-card class="section-card">
            <template #header>
              <div class="card-header">
                <span>待备货申请</span>
                <el-tag v-if="pendingSpareRequests.length > 0" type="danger" size="small">{{ pendingSpareRequests.length }} 个待处理</el-tag>
              </div>
            </template>
            <div v-if="pendingSpareRequests.length === 0" class="empty-state">暂无待处理的备件申请</div>
            <div v-for="req in pendingSpareRequests" :key="req.id" class="spare-request-item">
              <div class="request-info">
                <el-tag size="small" type="danger">紧急</el-tag>
                <span class="request-desc">{{ req.item_name }} x {{ req.quantity }}</span>
                <span class="request-ticket">工单: {{ req.ticket_id }}</span>
              </div>
              <div class="request-actions">
                <el-button type="success" size="small" @click="handleFulfill(req.id)">备货完成</el-button>
                <el-button type="danger" size="small" @click="handleReject(req.id)">拒绝</el-button>
              </div>
            </div>
          </el-card>

          <el-card class="section-card" style="margin-top: 16px">
            <template #header>
              <div class="card-header">
                <span>低库存告警</span>
                <el-tag v-if="lowStockItems.length > 0" type="warning" size="small">{{ lowStockItems.length }} 项</el-tag>
              </div>
            </template>
            <div v-if="lowStockItems.length === 0" class="empty-state">库存充足，无告警</div>
            <div v-for="item in lowStockItems" :key="item.id" class="low-stock-item">
              <el-icon color="#E6A23C"><WarningFilled /></el-icon>
              <span class="item-name">{{ item.name }}</span>
              <span class="item-quantity">剩余 {{ item.quantity }} {{ item.unit }} (阈值 {{ item.min_threshold }})</span>
              <el-button type="warning" size="small" @click="showStockInDialog(item)">入库</el-button>
            </div>
          </el-card>
        </el-col>

        <el-col :span="10">
          <el-card class="section-card chat-card">
            <template #header>
              <div class="card-header">
                <span>AI 助手</span>
                <span class="chat-hint">输入自然语言指令操作库房</span>
              </div>
            </template>
            <div class="chat-messages" ref="chatContainer">
              <div v-for="(msg, idx) in chatMessages" :key="idx" :class="['chat-message', msg.role]">
                <div class="message-content">{{ msg.content }}</div>
              </div>
            </div>
            <div class="chat-input">
              <el-input
                v-model="chatInput"
                placeholder="例如：入库 5 个 HP 12A 墨盒到 A 库"
                @keyup.enter="sendChatMessage"
                :disabled="!wsConnected"
              >
                <template #append>
                  <el-button @click="sendChatMessage" :disabled="!wsConnected">发送</el-button>
                </template>
              </el-input>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="section-card" style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>设备管理</span>
            <div class="header-actions">
              <el-select v-model="deviceLocationFilter" placeholder="筛选库房" clearable size="small" style="width: 120px" @change="loadDevices">
                <el-option v-for="loc in locations" :key="loc.id" :label="loc.name" :value="loc.id" />
              </el-select>
              <el-select v-model="deviceStatusFilter" placeholder="筛选状态" clearable size="small" style="width: 120px; margin-left: 8px" @change="loadDevices">
                <el-option label="在库" value="in_stock" />
                <el-option label="已分配" value="allocated" />
                <el-option label="使用中" value="in_use" />
                <el-option label="已损坏" value="damaged" />
                <el-option label="维修中" value="in_repair" />
                <el-option label="已修复" value="repaired" />
                <el-option label="已报废" value="scrapped" />
              </el-select>
              <el-input v-model="deviceSearch" placeholder="搜索设备" size="small" style="width: 200px; margin-left: 8px" clearable @keyup.enter="loadDevices" />
              <el-button type="primary" size="small" style="margin-left: 8px" @click="showCreateDeviceDialog">录入设备</el-button>
            </div>
          </div>
        </template>
        <el-table :data="devices" v-loading="devicesLoading" stripe style="width: 100%">
          <el-table-column prop="device_no" label="设备编码" width="160" />
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="model" label="型号" width="140" />
          <el-table-column prop="serial_number" label="序列号" width="140" />
          <el-table-column prop="category" label="类别" width="80">
            <template #default="{ row }">
              <el-tag size="small">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location_id" label="库房" width="120">
            <template #default="{ row }">
              <span v-if="row.location_id">{{ getLocationName(row.location_id) }}</span>
              <el-tag v-else type="info" size="small">未分配</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="statusColor(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showDeviceDetail(row)">详情</el-button>
              <el-dropdown v-if="getDeviceActions(row.status).length > 0" trigger="click" @command="(cmd: string) => handleDeviceAction(cmd, row)">
                <el-button size="small" type="primary">操作<el-icon><ArrowDown /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="action in getDeviceActions(row.status)" :key="action" :command="action">{{ deviceActionLabel(action) }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-row">
          <el-pagination v-model:current-page="devicePage" :page-size="20" :total="deviceTotal" layout="total, prev, pager, next" @current-change="loadDevices" />
        </div>
      </el-card>

      <el-card class="section-card" style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>库存/耗材管理</span>
            <div class="header-actions">
              <el-input v-model="inventorySearch" placeholder="搜索耗材" size="small" style="width: 200px" clearable @keyup.enter="loadInventory" />
              <el-button type="primary" size="small" style="margin-left: 8px" @click="showCreateInventoryDialog">添加耗材</el-button>
            </div>
          </div>
        </template>
        <el-table :data="inventoryItems" v-loading="inventoryLoading" stripe style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="category" label="类别" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.category || '耗材' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="model_spec" label="规格/型号" width="140" />
          <el-table-column prop="quantity" label="库存数量" width="100" sortable>
            <template #default="{ row }">
              <span :style="{ color: row.quantity <= row.min_threshold ? '#E6A23C' : '#303133', fontWeight: 'bold' }">{{ row.quantity }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="available_quantity" label="可用数量" width="100" />
          <el-table-column prop="unit" label="单位" width="70" />
          <el-table-column prop="min_threshold" label="最低阈值" width="90" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showStockInDialog(row)">入库</el-button>
              <el-button size="small" type="danger" @click="showStockOutDialog(row)">出库</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-row">
          <el-pagination v-model:current-page="inventoryPage" :page-size="20" :total="inventoryTotal" layout="total, prev, pager, next" @current-change="loadInventory" />
        </div>
      </el-card>

      <el-dialog v-model="deviceDetailVisible" title="设备详情" width="500px">
        <div v-if="selectedDevice" class="device-detail">
          <p><strong>编码:</strong> {{ selectedDevice.device_no }}</p>
          <p><strong>名称:</strong> {{ selectedDevice.name }}</p>
          <p><strong>型号:</strong> {{ selectedDevice.model || '未知' }}</p>
          <p><strong>序列号:</strong> {{ selectedDevice.serial_number || '未知' }}</p>
          <p><strong>状态:</strong> {{ statusLabel(selectedDevice.status) }}</p>
          <p><strong>品牌:</strong> {{ selectedDevice.brand || '未知' }}</p>
          <p><strong>所属库房:</strong> {{ selectedDevice.location_id ? getLocationName(selectedDevice.location_id) : '未分配' }}</p>
          <p><strong>购入价格:</strong> {{ selectedDevice.purchase_price || '未知' }}</p>
        </div>
      </el-dialog>
    </el-main>

    <el-dialog v-model="stockInDialogVisible" title="入库" width="400px">
      <el-form :model="stockInForm">
        <el-form-item label="物品"><span>{{ stockInForm.name }}</span></el-form-item>
        <el-form-item label="入库数量"><el-input-number v-model="stockInForm.quantity" :min="1" :max="9999" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="stockInForm.comment" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockInDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doStockIn" :loading="stockInLoading">确认入库</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDeviceDialogVisible" title="录入设备" width="500px">
      <el-form :model="createDeviceForm" label-position="top">
        <el-form-item label="设备名称"><el-input v-model="createDeviceForm.name" /></el-form-item>
        <el-form-item label="序列号"><el-input v-model="createDeviceForm.serial_number" /></el-form-item>
        <el-form-item label="型号"><el-input v-model="createDeviceForm.model" /></el-form-item>
        <el-form-item label="类别">
          <el-select v-model="createDeviceForm.category" style="width: 100%">
            <el-option label="打印机" value="printer" />
            <el-option label="电脑" value="computer" />
            <el-option label="网络设备" value="network" />
            <el-option label="服务器" value="server" />
            <el-option label="显示器" value="monitor" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="品牌"><el-input v-model="createDeviceForm.brand" /></el-form-item>
        <el-form-item label="所属库房">
          <el-select v-model="createDeviceForm.location_id" style="width: 100%" placeholder="选择库房" clearable>
            <el-option v-for="loc in locations" :key="loc.id" :label="loc.name" :value="loc.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDeviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doCreateDevice" :loading="createDeviceLoading">确认录入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="stockOutDialogVisible" title="出库" width="400px">
      <el-form :model="stockOutForm">
        <el-form-item label="物品"><span>{{ stockOutForm.name }}</span></el-form-item>
        <el-form-item label="当前库存"><span>{{ stockOutForm.currentQuantity }}</span></el-form-item>
        <el-form-item label="出库数量"><el-input-number v-model="stockOutForm.quantity" :min="1" :max="stockOutForm.currentQuantity" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="stockOutForm.comment" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockOutDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doStockOut" :loading="stockOutLoading">确认出库</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createInventoryDialogVisible" title="添加耗材" width="400px">
      <el-form :model="createInventoryForm" label-position="top">
        <el-form-item label="名称"><el-input v-model="createInventoryForm.name" /></el-form-item>
        <el-form-item label="类别"><el-input v-model="createInventoryForm.category" placeholder="如：键盘、鼠标、墨盒" /></el-form-item>
        <el-form-item label="规格/型号"><el-input v-model="createInventoryForm.model_spec" /></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="createInventoryForm.quantity" :min="1" :max="9999" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="createInventoryForm.unit" placeholder="个、箱、卷" /></el-form-item>
        <el-form-item label="最低阈值"><el-input-number v-model="createInventoryForm.min_threshold" :min="0" :max="9999" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createInventoryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doCreateInventory" :loading="createInventoryLoading">确认添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="transferDialogVisible" title="调配设备" width="400px">
      <el-form :model="transferForm" label-position="top">
        <el-form-item label="设备"><span>{{ transferForm.deviceName }}</span></el-form-item>
        <el-form-item label="当前库房"><span>{{ transferForm.currentLocation }}</span></el-form-item>
        <el-form-item label="调配至">
          <el-select v-model="transferForm.toLocationId" style="width: 100%" placeholder="选择目标库房">
            <el-option v-for="loc in transferTargetLocations" :key="loc.id" :label="loc.name" :value="loc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="transferForm.comment" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doTransfer" :loading="transferLoading">确认调配</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editLocationDialogVisible" title="编辑库房" width="400px">
      <el-form :model="editLocationForm" label-position="top">
        <el-form-item label="库房名称"><el-input v-model="editLocationForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="editLocationForm.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editLocationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doEditLocation" :loading="editLocationLoading">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createLocationDialogVisible" title="新增库房" width="400px">
      <el-form :model="createLocationForm" label-position="top">
        <el-form-item label="库房名称"><el-input v-model="createLocationForm.name" placeholder="如：A区库房" /></el-form-item>
        <el-form-item label="库房编码"><el-input v-model="createLocationForm.code" placeholder="如：WH-A" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createLocationForm.description" type="textarea" placeholder="库房位置、用途等" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createLocationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doCreateLocation" :loading="createLocationLoading">确认创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="statDetailVisible" :title="statDetailTitle" width="600px">
      <el-table :data="statDetailItems" v-loading="statDetailLoading" stripe max-height="400">
        <el-table-column prop="label" label="名称" min-width="200" />
        <el-table-column prop="value" label="数量" width="100">
          <template #default="{ row }">
            <span :style="{ fontWeight: 'bold', color: row.warning ? '#E6A23C' : '#303133' }">{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="extra" label="备注" min-width="150" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { WarningFilled, ArrowDown } from "@element-plus/icons-vue";
import { useStorekeeperWebSocket } from "../composables/useStorekeeperWebSocket";
import { warehouseAPI } from "../api";
import type {
  WarehouseOverview, WarehouseLocation, InventoryItem, DeviceItem, SparePartRequest,
} from "../types";
import { DEVICE_STATUS_LABELS, DEVICE_STATUS_COLORS, DEVICE_CATEGORY_LABELS } from "../types";

const router = useRouter();
const { messages: chatMessages, connected: wsConnected, connect: wsConnect, sendMessage: wsSend, disconnect: wsDisconnect } = useStorekeeperWebSocket();

const overview = ref<WarehouseOverview>({
  total_devices: 0, total_inventory_types: 0, low_stock_count: 0,
  pending_spare_requests: 0, damaged_count: 0, stock_in_this_month: 0, stock_out_this_month: 0,
});

const statsCards = ref<Array<{ label: string; value: number; alert?: string; alertType?: string; key?: string; clickable?: boolean }>>([]);

function updateStatsCards() {
  const o = overview.value;
  statsCards.value = [
    { label: "设备总数", value: o.total_devices, key: "devices" },
    { label: "库存种类", value: o.total_inventory_types, key: "inventory", clickable: true },
    { label: "低库存", value: o.low_stock_count, alert: o.low_stock_count > 0 ? "⚠" : "", alertType: "warning", key: "low_stock", clickable: true },
    { label: "待备货", value: o.pending_spare_requests, alert: o.pending_spare_requests > 0 ? "🔔" : "", alertType: "danger", key: "spare_requests", clickable: true },
    { label: "损坏", value: o.damaged_count, key: "damaged", clickable: true },
    { label: "本月入库", value: o.stock_in_this_month, key: "stock_in" },
  ];
}

async function loadOverview() {
  try {
    const { data } = await warehouseAPI.getStats();
    overview.value = data;
    updateStatsCards();
  } catch (e: any) {
    ElMessage.error("加载库房概览失败：" + (e.response?.data?.detail || e.message));
  }
}

const locations = ref<WarehouseLocation[]>([]);

async function loadLocations() {
  try {
    const { data } = await warehouseAPI.getLocations();
    locations.value = data;
  } catch (e: any) {
    ElMessage.error("加载库房列表失败");
  }
}

function getLocationName(locationId: string): string {
  const loc = locations.value.find(l => l.id === locationId);
  return loc ? loc.name : locationId;
}

const createLocationDialogVisible = ref(false);
const createLocationLoading = ref(false);
const createLocationForm = reactive({ name: "", code: "", description: "" });

function showCreateLocationDialog() {
  Object.assign(createLocationForm, { name: "", code: "", description: "" });
  createLocationDialogVisible.value = true;
}

async function doCreateLocation() {
  createLocationLoading.value = true;
  try {
    await warehouseAPI.createLocation({ ...createLocationForm });
    ElMessage.success("库房创建成功");
    createLocationDialogVisible.value = false;
    loadLocations();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    createLocationLoading.value = false;
  }
}

const editLocationDialogVisible = ref(false);
const editLocationLoading = ref(false);
const editLocationForm = reactive({ id: "", name: "", description: "" });

function showEditLocationDialog(loc: WarehouseLocation) {
  editLocationForm.id = loc.id;
  editLocationForm.name = loc.name;
  editLocationForm.description = loc.description || "";
  editLocationDialogVisible.value = true;
}

async function doEditLocation() {
  editLocationLoading.value = true;
  try {
    await warehouseAPI.updateLocation(editLocationForm.id, { name: editLocationForm.name, description: editLocationForm.description });
    ElMessage.success("库房编辑成功");
    editLocationDialogVisible.value = false;
    loadLocations();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "编辑失败");
  } finally {
    editLocationLoading.value = false;
  }
}

async function handleDeleteLocation(loc: WarehouseLocation) {
  try {
    await ElMessageBox.confirm(`确定删除库房"${loc.name}"吗？`, "确认删除", { type: "warning" });
    await warehouseAPI.deleteLocation(loc.id);
    ElMessage.success("库房已删除");
    loadLocations();
    loadOverview();
  } catch (e: any) {
    if (e !== "cancel") {
      ElMessage.error(e.response?.data?.detail || "删除失败");
    }
  }
}

const transferDialogVisible = ref(false);
const transferLoading = ref(false);
const transferForm = reactive({ deviceId: "", deviceName: "", currentLocation: "", toLocationId: "", comment: "" });
const transferTargetLocations = computed(() => {
  return locations.value.filter((loc) => loc.id !== transferForm.currentLocation);
});

function showTransferDialog(device: DeviceItem) {
  transferForm.deviceId = device.id;
  transferForm.deviceName = device.name;
  transferForm.currentLocation = device.location_id || "";
  transferForm.toLocationId = "";
  transferForm.comment = "";
  transferDialogVisible.value = true;
}

async function doTransfer() {
  if (!transferForm.toLocationId) { ElMessage.warning("请选择目标库房"); return; }
  transferLoading.value = true;
  try {
    await warehouseAPI.transferDevice(transferForm.deviceId, { to_location_id: transferForm.toLocationId, comment: transferForm.comment });
    ElMessage.success("设备调配成功");
    transferDialogVisible.value = false;
    loadDevices();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "调配失败");
  } finally {
    transferLoading.value = false;
  }
}

const lowStockItems = ref<InventoryItem[]>([]);

async function loadLowStock() {
  try {
    const { data } = await warehouseAPI.getInventory({ page: 1, page_size: 20, low_stock_only: true });
    lowStockItems.value = data.items;
  } catch (e: any) {
    ElMessage.error("加载低库存告警失败");
  }
}

const pendingSpareRequests = ref<SparePartRequest[]>([]);

async function loadPendingSpareRequests() {
  try {
    const { data } = await warehouseAPI.getSpareRequests({ status: "pending" });
    pendingSpareRequests.value = data.items;
  } catch (e: any) {
    ElMessage.error("加载备件申请失败");
  }
}

async function handleFulfill(id: string) {
  try {
    await warehouseAPI.fulfillSpareRequest(id);
    ElMessage.success("备货完成");
    loadPendingSpareRequests();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "备货失败");
  }
}

async function handleReject(id: string) {
  try {
    const { value: reason } = await ElMessageBox.prompt("请输入拒绝原因", "拒绝备件申请");
    await warehouseAPI.rejectSpareRequest(id, reason || "库存不足");
    ElMessage.success("已拒绝");
    loadPendingSpareRequests();
  } catch {
    // cancelled
  }
}

const devices = ref<DeviceItem[]>([]);
const deviceTotal = ref(0);
const devicePage = ref(1);
const deviceStatusFilter = ref("");
const deviceLocationFilter = ref("");
const deviceSearch = ref("");
const devicesLoading = ref(false);

async function loadDevices() {
  devicesLoading.value = true;
  try {
    const params: any = { page: devicePage.value, page_size: 20 };
    if (deviceStatusFilter.value) params.status = deviceStatusFilter.value;
    if (deviceLocationFilter.value) params.location_id = deviceLocationFilter.value;
    if (deviceSearch.value) params.search = deviceSearch.value;
    const { data } = await warehouseAPI.getDevices(params);
    devices.value = data.items;
    deviceTotal.value = data.total;
  } catch (e: any) {
    ElMessage.error("加载设备列表失败");
  } finally {
    devicesLoading.value = false;
  }
}

function statusLabel(status: string) { return DEVICE_STATUS_LABELS[status] || status; }
function statusColor(status: string) { return DEVICE_STATUS_COLORS[status] || "info"; }
function categoryLabel(category: string) { return DEVICE_CATEGORY_LABELS[category] || category; }

const DEVICE_ACTIONS: Record<string, string[]> = {
  in_stock: ["allocate", "transfer", "scrap"],
  allocated: ["deliver", "cancel_allocate", "transfer"],
  in_use: ["return_damaged", "transfer"],
  damaged: ["send_repair", "transfer", "scrap"],
  in_repair: ["repair_done", "transfer"],
  repaired: ["restock", "transfer", "scrap"],
};

const DEVICE_ACTION_LABELS: Record<string, string> = {
  allocate: "分配", scrap: "报废", deliver: "出库", cancel_allocate: "取消分配",
  return_damaged: "退回损坏", send_repair: "送修", repair_done: "修复完成",
  restock: "重新入库", transfer: "调配",
};

function getDeviceActions(status: string): string[] { return DEVICE_ACTIONS[status] || []; }
function deviceActionLabel(action: string): string { return DEVICE_ACTION_LABELS[action] || action; }

async function handleDeviceAction(action: string, device: DeviceItem) {
  if (action === "transfer") { showTransferDialog(device); return; }
  try {
    await warehouseAPI.deviceStatusChange(device.id, { action, comment: `手动操作: ${action}` });
    ElMessage.success(`操作成功: ${action}`);
    loadDevices();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "操作失败");
  }
}

const deviceDetailVisible = ref(false);
const selectedDevice = ref<DeviceItem | null>(null);

function showDeviceDetail(device: DeviceItem) {
  selectedDevice.value = device;
  deviceDetailVisible.value = true;
}

const stockInDialogVisible = ref(false);
const stockInLoading = ref(false);
const stockInForm = reactive({ id: "", name: "", quantity: 1, comment: "" });

function showStockInDialog(item: InventoryItem) {
  stockInForm.id = item.id;
  stockInForm.name = item.name;
  stockInForm.quantity = 1;
  stockInForm.comment = "";
  stockInDialogVisible.value = true;
}

async function doStockIn() {
  stockInLoading.value = true;
  try {
    await warehouseAPI.stockIn(stockInForm.id, { quantity: stockInForm.quantity, comment: stockInForm.comment });
    ElMessage.success(`已入库 ${stockInForm.quantity} 个 ${stockInForm.name}`);
    stockInDialogVisible.value = false;
    loadLowStock();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "入库失败");
  } finally {
    stockInLoading.value = false;
  }
}

const createDeviceDialogVisible = ref(false);
const createDeviceLoading = ref(false);
const createDeviceForm = reactive({ name: "", serial_number: "", model: "", category: "other", brand: "", location_id: "" });

function showCreateDeviceDialog() {
  Object.assign(createDeviceForm, { name: "", serial_number: "", model: "", category: "other", brand: "", location_id: "" });
  createDeviceDialogVisible.value = true;
}

async function doCreateDevice() {
  createDeviceLoading.value = true;
  try {
    await warehouseAPI.createDevice({ ...createDeviceForm });
    ElMessage.success("设备录入成功");
    createDeviceDialogVisible.value = false;
    loadDevices();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "录入失败");
  } finally {
    createDeviceLoading.value = false;
  }
}

const inventoryItems = ref<InventoryItem[]>([]);
const inventoryTotal = ref(0);
const inventoryPage = ref(1);
const inventorySearch = ref("");
const inventoryLoading = ref(false);

async function loadInventory() {
  inventoryLoading.value = true;
  try {
    const params: any = { page: inventoryPage.value, page_size: 20 };
    if (inventorySearch.value) params.search = inventorySearch.value;
    const { data } = await warehouseAPI.getInventory(params);
    inventoryItems.value = data.items;
    inventoryTotal.value = data.total;
  } catch (e: any) {
    ElMessage.error("加载库存列表失败");
  } finally {
    inventoryLoading.value = false;
  }
}

const stockOutDialogVisible = ref(false);
const stockOutLoading = ref(false);
const stockOutForm = reactive({ id: "", name: "", currentQuantity: 0, quantity: 1, comment: "" });

function showStockOutDialog(item: InventoryItem) {
  stockOutForm.id = item.id;
  stockOutForm.name = item.name;
  stockOutForm.currentQuantity = item.quantity;
  stockOutForm.quantity = 1;
  stockOutForm.comment = "";
  stockOutDialogVisible.value = true;
}

async function doStockOut() {
  stockOutLoading.value = true;
  try {
    await warehouseAPI.stockOut(stockOutForm.id, { quantity: stockOutForm.quantity, comment: stockOutForm.comment });
    ElMessage.success(`已出库 ${stockOutForm.quantity} 个 ${stockOutForm.name}`);
    stockOutDialogVisible.value = false;
    loadInventory();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "出库失败");
  } finally {
    stockOutLoading.value = false;
  }
}

const createInventoryDialogVisible = ref(false);
const createInventoryLoading = ref(false);
const createInventoryForm = reactive({ name: "", category: "", model_spec: "", quantity: 1, unit: "个", min_threshold: 5 });

function showCreateInventoryDialog() {
  Object.assign(createInventoryForm, { name: "", category: "", model_spec: "", quantity: 1, unit: "个", min_threshold: 5 });
  createInventoryDialogVisible.value = true;
}

async function doCreateInventory() {
  createInventoryLoading.value = true;
  try {
    await warehouseAPI.createInventory({ ...createInventoryForm });
    ElMessage.success("耗材添加成功");
    createInventoryDialogVisible.value = false;
    loadInventory();
    loadOverview();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "添加失败");
  } finally {
    createInventoryLoading.value = false;
  }
}

const statDetailVisible = ref(false);
const statDetailTitle = ref("");
const statDetailItems = ref<Array<{ label: string; value: number | string; extra?: string; warning?: boolean }>>([]);
const statDetailLoading = ref(false);

async function handleStatClick(stat: any) {
  if (!stat.clickable) return;
  statDetailTitle.value = stat.label;
  statDetailLoading.value = true;
  statDetailVisible.value = true;

  try {
    if (stat.key === "inventory") {
      const { data } = await warehouseAPI.getInventory({ page: 1, page_size: 100 });
      statDetailItems.value = data.items.map((item: InventoryItem) => ({
        label: item.name, value: item.quantity,
        extra: `${item.category || '耗材'} | 可用: ${item.available_quantity} | 阈值: ${item.min_threshold}`,
        warning: item.quantity <= item.min_threshold,
      }));
    } else if (stat.key === "low_stock") {
      const { data } = await warehouseAPI.getInventory({ page: 1, page_size: 100, low_stock_only: true });
      statDetailItems.value = data.items.map((item: InventoryItem) => ({
        label: item.name, value: item.quantity,
        extra: `阈值: ${item.min_threshold} | 可用: ${item.available_quantity}`,
        warning: true,
      }));
    } else if (stat.key === "spare_requests") {
      const { data } = await warehouseAPI.getSpareRequests({ status: "pending" });
      statDetailItems.value = data.items.map((req: SparePartRequest) => ({
        label: req.item_name, value: req.quantity,
        extra: `工单: ${req.ticket_id} | 状态: ${req.status}`,
      }));
    } else if (stat.key === "damaged") {
      const { data } = await warehouseAPI.getDevices({ page: 1, page_size: 100, status: "damaged" });
      statDetailItems.value = data.items.map((d: DeviceItem) => ({
        label: `${d.name} (${d.device_no})`, value: d.status,
        extra: `型号: ${d.model || '未知'} | 序列号: ${d.serial_number || '未知'}`,
      }));
    } else if (stat.key === "devices") {
      const { data } = await warehouseAPI.getDevices({ page: 1, page_size: 100 });
      statDetailItems.value = data.items.map((d: DeviceItem) => ({
        label: `${d.name} (${d.device_no})`, value: statusLabel(d.status),
        extra: `型号: ${d.model || '未知'}`,
      }));
    }
  } catch (e: any) {
    ElMessage.error("加载详情失败");
  } finally {
    statDetailLoading.value = false;
  }
}

const chatInput = ref("");
const chatContainer = ref<HTMLElement>();

function sendChatMessage() {
  const msg = chatInput.value.trim();
  if (!msg) return;
  wsSend(msg);
  chatInput.value = "";
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  });
}

function handleLogout() {
  wsDisconnect();
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  router.push("/login");
}

onMounted(() => {
  wsConnect();
  loadLocations();
  loadOverview();
  loadLowStock();
  loadPendingSpareRequests();
  loadDevices();
  loadInventory();
});
</script>

<style scoped>
.storekeeper-dashboard { min-height: 100vh; background: #f5f7fa; }
.dashboard-header { display: flex; justify-content: space-between; align-items: center; background: #fff; padding: 0 24px; height: 56px; border-bottom: 1px solid #e4e7ed; }
.dashboard-header h2 { margin: 0; font-size: 18px; color: #303133; }
.header-right { display: flex; align-items: center; gap: 12px; }
.dashboard-main { padding: 16px 24px; }
.stats-row { margin-bottom: 0; }
.stat-card { text-align: center; }
.stat-card.clickable { cursor: pointer; }
.stat-card-wrapper:hover .stat-card.clickable { color: #409eff; }
.stat-value { font-size: 28px; font-weight: 700; color: #303133; line-height: 1.2; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.section-card { margin-bottom: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; align-items: center; }
.chat-hint { font-size: 12px; color: #909399; }
.empty-state { color: #909399; text-align: center; padding: 24px 0; font-size: 14px; }
.spare-request-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.spare-request-item:last-child { border-bottom: none; }
.request-info { display: flex; align-items: center; gap: 8px; }
.request-desc { font-weight: 500; }
.request-ticket { color: #909399; font-size: 12px; }
.low-stock-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.low-stock-item:last-child { border-bottom: none; }
.item-name { font-weight: 500; }
.item-quantity { color: #909399; font-size: 13px; flex: 1; }
.chat-card { height: 100%; }
.chat-messages { height: 300px; overflow-y: auto; padding: 8px; background: #fafafa; border-radius: 4px; margin-bottom: 12px; }
.chat-message { margin-bottom: 8px; padding: 8px 12px; border-radius: 8px; max-width: 85%; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
.chat-message.user { background: #409eff; color: #fff; margin-left: auto; }
.chat-message.assistant { background: #fff; border: 1px solid #e4e7ed; }
.location-card { text-align: center; }
.location-name { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 4px; }
.location-code { font-size: 12px; color: #909399; margin-bottom: 4px; }
.location-desc { font-size: 12px; color: #909399; margin-bottom: 6px; }
.location-actions { margin-top: 8px; display: flex; justify-content: center; gap: 4px; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>