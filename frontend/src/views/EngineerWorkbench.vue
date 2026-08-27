<template>
  <div class="engineer-workbench">
    <h2 class="page-title">工程师工作台</h2>

    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="4">
          <el-select v-model="filterStatus" placeholder="状态筛选" clearable @change="fetchTickets">
            <el-option label="已分配" value="assigned" />
            <el-option label="处理中" value="in_progress" />
            <el-option label="已解决" value="resolved" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchTickets">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tickets" border stripe v-loading="loading" style="width: 100%" @expand-change="handleExpand">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="ticket-detail">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="工单号">{{ row.ticket_no }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="标题" :span="2">{{ row.title }}</el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">{{ row.description || '无' }}</el-descriptions-item>
                <el-descriptions-item label="故障分类">{{ row.fault_category || '-' }}</el-descriptions-item>
                <el-descriptions-item label="紧急程度">
                  <el-tag :type="urgencyType(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="位置">{{ row.location || '-' }}</el-descriptions-item>
                <el-descriptions-item label="SLA 截止时间">{{ formatTime(row.sla_deadline) }}</el-descriptions-item>
                <el-descriptions-item label="解决方案" :span="2">{{ row.resolution || '暂无' }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ formatTime(row.created_at) }}</el-descriptions-item>
                <el-descriptions-item label="解决时间">{{ formatTime(row.resolved_at) }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="ticket_no" label="工单号" width="180" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="紧急程度" width="100">
          <template #default="{ row }">
            <el-tag :type="urgencyType(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SLA截止" width="170">
          <template #default="{ row }">
            <span :class="{ 'sla-overdue': isSlaOverdue(row.sla_deadline) }">
              {{ formatTime(row.sla_deadline) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="acceptTicket(row)" :disabled="row.status !== 'assigned'">
              接单
            </el-button>
            <el-button size="small" type="warning" @click="rejectTicket(row)" :disabled="row.status !== 'assigned'">
              拒单
            </el-button>
            <el-button size="small" type="success" @click="resolveTicket(row)" :disabled="row.status !== 'in_progress'">
              解决
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchTickets"
          @current-change="fetchTickets"
        />
      </div>
    </el-card>

    <el-dialog v-model="showRejectDialog" title="拒单" width="500px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ rejectTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="拒单原因">
          <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请输入拒单原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="warning" @click="doReject" :loading="rejecting">确认拒单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResolveDialog" title="提交解决方案" width="500px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ resolveTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="解决方案" required>
          <el-input v-model="resolution" type="textarea" :rows="4" placeholder="请输入解决方案" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResolveDialog = false">取消</el-button>
        <el-button type="success" @click="doResolve" :loading="resolving">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, adminAPI } from "../api";
import type { Ticket } from "../types";

const tickets = ref<Ticket[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

const filterStatus = ref("");

const showRejectDialog = ref(false);
const rejectTarget = ref<Ticket | null>(null);
const rejectReason = ref("");
const rejecting = ref(false);

const showResolveDialog = ref(false);
const resolveTarget = ref<Ticket | null>(null);
const resolution = ref("");
const resolving = ref(false);

function statusType(status: string) {
  const map: Record<string, string> = {
    created: "info", assigned: "warning", in_progress: "primary",
    resolved: "success", closed: "default", cancelled: "danger",
  };
  return map[status] || "info";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    created: "已创建", assigned: "已分配", in_progress: "处理中",
    resolved: "已解决", closed: "已关闭", cancelled: "已取消",
  };
  return map[status] || status;
}

function urgencyType(urgency: string) {
  const map: Record<string, string> = { low: "info", medium: "warning", high: "danger", critical: "danger" };
  return map[urgency] || "info";
}

function urgencyLabel(urgency: string) {
  const map: Record<string, string> = { low: "低", medium: "中", high: "高", critical: "紧急" };
  return map[urgency] || urgency;
}

function formatTime(t: string | undefined) {
  if (!t) return "-";
  return new Date(t).toLocaleString("zh-CN");
}

function isSlaOverdue(slaDeadline: string | undefined) {
  if (!slaDeadline) return false;
  return new Date(slaDeadline) < new Date();
}

async function fetchTickets() {
  loading.value = true;
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value };
    if (filterStatus.value) params.status = filterStatus.value;
    const res = await adminAPI.getTickets(params);
    tickets.value = res.data.items;
    total.value = res.data.total;
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "获取工单列表失败");
  } finally {
    loading.value = false;
  }
}

function handleExpand(row: Ticket, expandedRows: Ticket[]) {
  // 展开行时无需额外操作
}

async function acceptTicket(ticket: Ticket) {
  try {
    await ElMessageBox.confirm(`确定要接单 ${ticket.ticket_no} 吗？`, "接单确认", { type: "info" });
    await adminAPI.acceptTicket(ticket.id);
    ElMessage.success("接单成功");
    fetchTickets();
  } catch (e: any) {
    if (e !== "cancel") {
      ElMessage.error(e.response?.data?.detail || "接单失败");
    }
  }
}

function rejectTicket(ticket: Ticket) {
  rejectTarget.value = ticket;
  rejectReason.value = "";
  showRejectDialog.value = true;
}

async function doReject() {
  if (!rejectTarget.value) return;
  rejecting.value = true;
  try {
    await adminAPI.rejectTicket(rejectTarget.value.id, rejectReason.value || undefined);
    ElMessage.success("已拒单");
    showRejectDialog.value = false;
    fetchTickets();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "拒单失败");
  } finally {
    rejecting.value = false;
  }
}

function resolveTicket(ticket: Ticket) {
  resolveTarget.value = ticket;
  resolution.value = "";
  showResolveDialog.value = true;
}

async function doResolve() {
  if (!resolveTarget.value) return;
  if (!resolution.value.trim()) { ElMessage.warning("请输入解决方案"); return; }
  resolving.value = true;
  try {
    await adminAPI.resolveTicket(resolveTarget.value.id, resolution.value);
    ElMessage.success("解决方案已提交");
    showResolveDialog.value = false;
    fetchTickets();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "提交失败");
  } finally {
    resolving.value = false;
  }
}

onMounted(() => {
  fetchTickets();
});
</script>

<style scoped>
.engineer-workbench { padding: 20px; min-height: 100vh; background: #f0f2f5; }
.page-title { margin: 0 0 16px 0; font-size: 20px; padding: 0 4px; }
.filter-card { margin-bottom: 16px; }
.table-card { margin-bottom: 16px; }
.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 16px; }
.ticket-detail { padding: 16px 24px; background: #fafafa; }
.sla-overdue { color: #f56c6c; font-weight: bold; }
</style>