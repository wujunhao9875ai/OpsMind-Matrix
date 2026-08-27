<template>
  <div class="session-sidebar" :class="{ collapsed: store.sidebarCollapsed }">
    <!-- 顶部：Logo + 新对话按钮 -->
    <div class="sidebar-header">
      <div class="logo-area">
        <span class="logo-icon">&#9670;</span>
        <span class="logo-text">运维 AI</span>
      </div>
      <button class="new-chat-btn" @click="onNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>新对话</span>
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="session-list" ref="listRef">
      <template v-for="group in groupedSessions" :key="group.label">
        <div class="group-label">{{ group.label }}</div>
        <div
          v-for="sess in group.sessions"
          :key="sess.id"
          :class="['session-item', { active: store.currentSessionId === sess.id }]"
          @click="onSelect(sess.id)"
        >
          <div class="session-title">{{ sess.title || '新对话' }}</div>
          <div class="session-actions">
            <span class="session-count" v-if="sess.message_count > 0">{{ sess.message_count }}</span>
            <button
              class="delete-btn"
              title="删除会话"
              @click.stop="onDelete(sess.id)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      </template>

      <div v-if="store.sessions.length === 0 && store.sessionsLoaded" class="empty-hint">
        暂无对话记录
      </div>
    </div>

    <!-- 底部：用户信息 -->
    <div class="sidebar-footer">
      <div class="user-avatar">{{ store.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
      <div class="user-name">{{ store.username || '用户' }}</div>
      <button class="logout-btn" title="退出登录" @click="onLogout">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '../stores/chat'
import type { ChatSession } from '../types'

const store = useChatStore()
const router = useRouter()
const listRef = ref<HTMLElement>()

const emit = defineEmits<{
  newChat: []
  select: [sessionId: string]
  delete: [sessionId: string]
}>()

// 日期分组
const groupedSessions = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const last7Days = new Date(today.getTime() - 7 * 86400000)
  const last30Days = new Date(today.getTime() - 30 * 86400000)

  const groups: { label: string; sessions: ChatSession[] }[] = [
    { label: '今天', sessions: [] },
    { label: '昨天', sessions: [] },
    { label: '7 天内', sessions: [] },
    { label: '30 天内', sessions: [] },
    { label: '更早', sessions: [] },
  ]

  for (const s of store.sessions) {
    const d = new Date(s.updated_at)
    if (d >= today) {
      groups[0].sessions.push(s)
    } else if (d >= yesterday) {
      groups[1].sessions.push(s)
    } else if (d >= last7Days) {
      groups[2].sessions.push(s)
    } else if (d >= last30Days) {
      groups[3].sessions.push(s)
    } else {
      groups[4].sessions.push(s)
    }
  }

  return groups.filter(g => g.sessions.length > 0)
})

function onNewChat() {
  emit('newChat')
}

function onSelect(id: string) {
  emit('select', id)
}

async function onDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await store.deleteSession(id)
  } catch {
    // 取消
  }
}

function onLogout() {
  store.logout()
  router.push('/login')
}

onMounted(() => {
  store.loadSessions()
})
</script>

<style scoped>
.session-sidebar {
  width: 260px;
  min-width: 260px;
  height: 100vh;
  background: #f9fafb;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  transition: width 0.2s, min-width 0.2s;
}
.session-sidebar.collapsed {
  width: 0;
  min-width: 0;
  overflow: hidden;
}

/* 头部 */
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.logo-area {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.logo-icon {
  font-size: 22px;
  color: #4f6bed;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}
.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.new-chat-btn:hover {
  background: #f3f4f6;
  border-color: #4f6bed;
  color: #4f6bed;
}

/* 会话列表 */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.group-label {
  font-size: 11px;
  color: #9ca3af;
  padding: 8px 8px 4px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s;
  margin-bottom: 2px;
}
.session-item:hover {
  background: #e5e7eb;
}
.session-item.active {
  background: #e8edfb;
}
.session-item.active .session-title {
  color: #4f6bed;
  font-weight: 500;
}
.session-title {
  flex: 1;
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.session-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 8px;
}
.session-count {
  font-size: 11px;
  color: #9ca3af;
  background: #e5e7eb;
  padding: 1px 6px;
  border-radius: 10px;
}
.delete-btn {
  display: none;
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.1s;
}
.session-item:hover .delete-btn {
  display: flex;
}
.delete-btn:hover {
  color: #ef4444;
  background: #fef2f2;
}
.empty-hint {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 32px 16px;
}

/* 底部 */
.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #4f6bed;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout-btn {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.1s;
}
.logout-btn:hover {
  color: #ef4444;
  background: #fef2f2;
}
</style>