<template>
  <div class="admin-dashboard">
    <h2 class="page-title">运维派单管理后台</h2>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>工单总数</template>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>待分配</template>
          <div class="stat-value">{{ sla.unassigned }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>处理中</template>
          <div class="stat-value">{{ (stats.by_status?.in_progress || 0) + (stats.by_status?.assigned || 0) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>已解决</template>
          <div class="stat-value">{{ stats.by_status?.resolved || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>SLA 超期</template>
          <div class="stat-value danger">{{ sla.overdue }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <template #header>已关闭</template>
          <div class="stat-value">{{ stats.by_status?.closed || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>低优先级</template>
          <div class="stat-value">{{ stats.by_urgency?.low || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>中优先级</template>
          <div class="stat-value">{{ stats.by_urgency?.medium || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>高优先级</template>
          <div class="stat-value">{{ stats.by_urgency?.high || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>紧急</template>
          <div class="stat-value">{{ stats.by_urgency?.critical || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="4">
          <el-select v-model="filterStatus" placeholder="状态筛选" clearable @change="fetchTickets">
            <el-option label="已创建" value="created" />
            <el-option label="已分配" value="assigned" />
            <el-option label="处理中" value="in_progress" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已关闭" value="closed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filterUrgency" placeholder="紧急程度" clearable @change="fetchTickets">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="showCreateDialog = true">创建工单</el-button>
        </el-col>
        <el-col :span="4">
          <el-button @click="showEngineerDialog = true">工程师管理</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tickets" border stripe v-loading="loading" style="width: 100%">
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
        <el-table-column label="指派给" width="100">
          <template #default="{ row }">
            {{ getEngineerForTicket(row)?.display_name || row.assigned_to || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="400" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="assignTicket(row)" :disabled="!canAssign(row)">指派</el-button>
            <el-button size="small" type="warning" @click="reassignTicket(row)" :disabled="!canReassign(row)">改派</el-button>
            <el-button size="small" @click="changePriority(row)">优先级</el-button>
            <el-dropdown @command="(cmd: string) => handleAction(cmd, row)" style="margin-left: 4px">
              <el-button size="small">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="close" :disabled="!canClose(row)">关闭</el-dropdown-item>
                  <el-dropdown-item command="reopen" :disabled="row.status !== 'closed'">重新打开</el-dropdown-item>
                  <el-dropdown-item command="cancel" :disabled="row.status === 'closed' || row.status === 'cancelled'">取消</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

    <el-dialog v-model="showCreateDialog" title="创建工单" width="600px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="请输入工单标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入工单描述" />
        </el-form-item>
        <el-form-item label="故障分类">
          <el-select v-model="createForm.fault_category" style="width: 100%">
            <el-option label="硬件故障" value="hardware" />
            <el-option label="软件故障" value="software" />
            <el-option label="网络故障" value="network" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="紧急程度">
          <el-select v-model="createForm.urgency" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="createForm.location" placeholder="请输入位置信息" />
        </el-form-item>
        <el-form-item label="指派工程师">
          <el-select v-model="createForm.engineer_id" placeholder="不选择则自动分配" clearable style="width: 100%">
            <el-option v-for="e in engineers" :key="e.id" :label="e.display_name" :value="e.user_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreateTicket" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAssignDialog" title="指派工单" width="500px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ assignTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="指派给">
          <el-select v-model="assignEngineerId" placeholder="不选择则自动分配" clearable style="width: 100%">
            <el-option v-for="e in engineers" :key="e.id" :label="e.display_name" :value="e.user_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" @click="doAssign" :loading="assigning">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReassignDialog" title="改派工单" width="520px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 16px">
        <template #title>
          改派将自动提升优先级：{{ reassignTarget ? urgencyLabel(reassignTarget.urgency) + ' → ' + nextUrgencyLabel(reassignTarget.urgency) : '' }}
        </template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ reassignTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="当前优先级">
          <el-tag :type="reassignTarget ? urgencyType(reassignTarget.urgency) : 'info'" size="small">{{ reassignTarget ? urgencyLabel(reassignTarget.urgency) : '' }}</el-tag>
        </el-form-item>
        <el-form-item label="改派给" required>
          <el-select v-model="reassignEngineerId" placeholder="请选择工程师" style="width: 100%">
            <el-option v-for="e in engineers" :key="e.id" :label="e.display_name" :value="e.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="改派原因" required>
          <el-input v-model="reassignReason" type="textarea" :rows="2" placeholder="请说明改派原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReassignDialog = false">取消</el-button>
        <el-button type="danger" @click="doReassign" :loading="reassigning">确认改派</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPriorityDialog" title="变更优先级" width="400px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ priorityTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="紧急程度" required>
          <el-select v-model="newPriority" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPriorityDialog = false">取消</el-button>
        <el-button type="primary" @click="doChangePriority" :loading="priorityChanging">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCancelDialog" title="取消工单" width="400px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ cancelTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="取消原因">
          <el-input v-model="cancelReason" placeholder="请输入取消原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCancelDialog = false">取消</el-button>
        <el-button type="danger" @click="doCancel" :loading="cancelling">确认取消</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReopenDialog" title="重新打开工单" width="400px">
      <el-form label-width="100px">
        <el-form-item label="工单号">
          <span>{{ reopenTarget?.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="reopenReason" placeholder="请输入重新打开原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReopenDialog = false">取消</el-button>
        <el-button type="primary" @click="doReopen" :loading="reopening">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEngineerDialog" title="工程师管理" width="700px">
      <div style="margin-bottom: 12px">
        <el-button type="primary" @click="showAddEngineerForm = true" v-if="!showAddEngineerForm">添加工程师</el-button>
      </div>
      <el-form v-if="showAddEngineerForm" :model="engineerForm" label-width="100px" style="margin-bottom: 16px">
        <el-form-item label="用户ID" required>
          <el-input v-model="engineerForm.user_id" placeholder="请输入用户ID" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="engineerForm.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="技能">
          <el-input v-model="engineerForm.skills_input" placeholder="用逗号分隔多个技能" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doCreateEngineer" :loading="creatingEngineer">保存</el-button>
          <el-button @click="showAddEngineerForm = false">取消</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="engineers" border stripe style="width: 100%">
        <el-table-column prop="display_name" label="姓名" width="120" />
        <el-table-column prop="user_id" label="用户ID" width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="engStatusType(row.status)" size="small">{{ engStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="技能" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="s in row.skills" :key="s" size="small" style="margin-right: 4px">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="负载" width="80">
          <template #default="{ row }">
            {{ row.current_load }}/{{ row.max_concurrent }}
          </template>
        </el-table-column>
        <el-table-column label="评分" width="80">
          <template #default="{ row }">
            {{ row.rating?.toFixed(1) || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, adminAPI } from "../api";
import type { Ticket, Engineer, TicketStats, SlaStats } from "../types";

const tickets = ref<Ticket[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

const stats = reactive<TicketStats>({ total: 0, by_status: {}, by_urgency: {} });
const sla = reactive<SlaStats>({ overdue: 0, unassigned: 0 });

const filterStatus = ref("");
const filterUrgency = ref("");

const engineers = ref<Engineer[]>([]);

const engineerMap = computed(() => {
  const map: Record<string, Engineer> = {};
  engineers.value.forEach((e: Engineer) => {
    map[e.user_id] = e;
  });
  return map;
});

function getEngineerForTicket(ticket: Ticket): Engineer | undefined {
  if (!ticket.assigned_to) return undefined;
  return engineerMap.value[ticket.assigned_to];
}

const showCreateDialog = ref(false);
const creating = ref(false);
const createForm = reactive({
  title: "",
  description: "",
  fault_category: "other" as string,
  urgency: "medium" as string,
  location: "",
  engineer_id: "" as string | undefined,
});

const showAssignDialog = ref(false);
const assignTarget = ref<Ticket | null>(null);
const assignEngineerId = ref<string>("");
const assigning = ref(false);

const showReassignDialog = ref(false);
const reassignTarget = ref<Ticket | null>(null);
const reassignEngineerId = ref("");
const reassignReason = ref("");
const reassigning = ref(false);

const showPriorityDialog = ref(false);
const priorityTarget = ref<Ticket | null>(null);
const newPriority = ref("medium");
const priorityChanging = ref(false);

const showCancelDialog = ref(false);
const cancelTarget = ref<Ticket | null>(null);
const cancelReason = ref("");
const cancelling = ref(false);

const showReopenDialog = ref(false);
const reopenTarget = ref<Ticket | null>(null);
const reopenReason = ref("");
const reopening = ref(false);

const showEngineerDialog = ref(false);
const showAddEngineerForm = ref(false);
const creatingEngineer = ref(false);
const engineerForm = reactive({
  user_id: "",
  display_name: "",
  skills_input: "",
});

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

function engStatusType(status: string) {
  const map: Record<string, string> = { available: "success", busy: "warning", offline: "info" };
  return map[status] || "info";
}

function engStatusLabel(status: string) {
  const map: Record<string, string> = { available: "空闲", busy: "忙碌", offline: "离线" };
  return map[status] || status;
}

function formatTime(t: string | undefined) {
  if (!t) return "-";
  return new Date(t).toLocaleString("zh-CN");
}

function canAssign(ticket: Ticket) { return ticket.status === "created"; }
function canReassign(ticket: Ticket) { return ticket.status === "assigned" || ticket.status === "in_progress"; }
function canClose(ticket: Ticket) { return ticket.status === "resolved"; }

async function fetchTickets() {
  loading.value = true;
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value };
    if (filterStatus.value) params.status = filterStatus.value;
    if (filterUrgency.value) params.urgency = filterUrgency.value;
    const res = await adminAPI.getTickets(params);
    const result = res.data.result || res.data;
    tickets.value = result.items || [];
    total.value = result.total || 0;
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "获取工单列表失败");
  } finally {
    loading.value = false;
  }
}

async function fetchStats() {
  try {
    const res = await adminAPI.getStats();
    const data = res.data.result || res.data;
    Object.assign(stats, { total: data.total || 0, by_status: data.by_status || {}, by_urgency: data.by_urgency || {} });
    Object.assign(sla, { overdue: data.overdue || 0, unassigned: data.unassigned || 0 });
  } catch {
    // 静默失败
  }
}

async function fetchEngineers() {
  try {
    const res = await adminAPI.getEngineers();
    const data = res.data.result || res.data;
    engineers.value = data.items || data;
  } catch {
    // 静默失败
  }
}

async function doCreateTicket() {
  if (!createForm.title) { ElMessage.warning("请输入工单标题"); return; }
  creating.value = true;
  try {
    await adminAPI.createTicket({
      title: createForm.title,
      description: createForm.description,
      fault_category: createForm.fault_category,
      urgency: createForm.urgency,
      location: createForm.location,
      engineer_id: createForm.engineer_id || undefined,
    });
    ElMessage.success("工单创建成功");
    showCreateDialog.value = false;
    resetCreateForm();
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建工单失败");
  } finally {
    creating.value = false;
  }
}

function resetCreateForm() {
  createForm.title = "";
  createForm.description = "";
  createForm.fault_category = "other";
  createForm.urgency = "medium";
  createForm.location = "";
  createForm.engineer_id = "";
}

function assignTicket(ticket: Ticket) {
  assignTarget.value = ticket;
  assignEngineerId.value = "";
  showAssignDialog.value = true;
}

async function doAssign() {
  if (!assignTarget.value) return;
  assigning.value = true;
  try {
    await adminAPI.assignTicket(assignTarget.value.id, assignEngineerId.value || undefined);
    ElMessage.success("指派成功");
    showAssignDialog.value = false;
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "指派失败");
  } finally {
    assigning.value = false;
  }
}

function reassignTicket(ticket: Ticket) {
  reassignTarget.value = ticket;
  reassignEngineerId.value = "";
  reassignReason.value = "";
  showReassignDialog.value = true;
}

async function doReassign() {
  if (!reassignTarget.value || !reassignEngineerId.value) { ElMessage.warning("请选择工程师"); return; }
  if (!reassignReason.value.trim()) { ElMessage.warning("请填写改派原因"); return; }
  reassigning.value = true;
  try {
    await adminAPI.reassignTicket(reassignTarget.value.id, reassignEngineerId.value, reassignReason.value);
    ElMessage.success("改派成功，优先级已自动提升");
    showReassignDialog.value = false;
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "改派失败");
  } finally {
    reassigning.value = false;
  }
}

function nextUrgencyLabel(urgency: string) {
  const order = ["low", "medium", "high", "critical"];
  const idx = order.indexOf(urgency);
  if (idx >= 0 && idx < order.length - 1) return urgencyLabel(order[idx + 1]);
  return urgencyLabel(urgency) + " (已是最高)";
}

function changePriority(ticket: Ticket) {
  priorityTarget.value = ticket;
  newPriority.value = ticket.urgency;
  showPriorityDialog.value = true;
}

async function doChangePriority() {
  if (!priorityTarget.value) return;
  priorityChanging.value = true;
  try {
    await adminAPI.changePriority(priorityTarget.value.id, newPriority.value);
    ElMessage.success("优先级变更成功");
    showPriorityDialog.value = false;
    fetchTickets();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "变更失败");
  } finally {
    priorityChanging.value = false;
  }
}

async function doCloseTicket(ticket: Ticket) {
  try {
    await ElMessageBox.confirm(`确定要关闭工单 ${ticket.ticket_no} 吗？`, "关闭工单", { type: "warning" });
    await adminAPI.closeTicket(ticket.id);
    ElMessage.success("工单已关闭");
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    if (e !== "cancel") {
      ElMessage.error(e.response?.data?.detail || "关闭失败");
    }
  }
}

function cancelTicket(ticket: Ticket) {
  cancelTarget.value = ticket;
  cancelReason.value = "";
  showCancelDialog.value = true;
}

async function doCancel() {
  if (!cancelTarget.value) return;
  cancelling.value = true;
  try {
    await adminAPI.cancelTicket(cancelTarget.value.id, cancelReason.value || undefined as any);
    ElMessage.success("工单已取消");
    showCancelDialog.value = false;
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "取消失败");
  } finally {
    cancelling.value = false;
  }
}

function reopenTicket(ticket: Ticket) {
  reopenTarget.value = ticket;
  reopenReason.value = "";
  showReopenDialog.value = true;
}

async function doReopen() {
  if (!reopenTarget.value) return;
  reopening.value = true;
  try {
    await adminAPI.reopenTicket(reopenTarget.value.id, reopenReason.value || undefined);
    ElMessage.success("工单已重新打开");
    showReopenDialog.value = false;
    fetchTickets();
    fetchStats();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "重新打开失败");
  } finally {
    reopening.value = false;
  }
}

function handleAction(cmd: string, ticket: Ticket) {
  switch (cmd) {
    case "close": doCloseTicket(ticket); break;
    case "reopen": reopenTicket(ticket); break;
    case "cancel": cancelTicket(ticket); break;
  }
}

async function doCreateEngineer() {
  if (!engineerForm.user_id || !engineerForm.display_name) { ElMessage.warning("请填写用户ID和显示名称"); return; }
  creatingEngineer.value = true;
  try {
    const skills = engineerForm.skills_input ? engineerForm.skills_input.split(",").map((s) => s.trim()).filter(Boolean) : [];
    await adminAPI.createEngineer({
      user_id: engineerForm.user_id,
      display_name: engineerForm.display_name,
      skills,
      skill_levels: {},
    });
    ElMessage.success("工程师创建成功");
    engineerForm.user_id = "";
    engineerForm.display_name = "";
    engineerForm.skills_input = "";
    showAddEngineerForm.value = false;
    fetchEngineers();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建工程师失败");
  } finally {
    creatingEngineer.value = false;
  }
}

onMounted(() => {
  fetchTickets();
  fetchStats();
  fetchEngineers();
});
</script>

<style scoped>
.admin-dashboard { padding: 20px; min-height: 100vh; background: #f0f2f5; }
.page-title { margin: 0 0 16px 0; font-size: 20px; padding: 0 4px; }
.stats-row { margin-bottom: 16px; }
.stats-row .el-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; }
.stat-value.danger { color: #f56c6c; }
.filter-card { margin-bottom: 16px; }
.table-card { margin-bottom: 16px; }
.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>