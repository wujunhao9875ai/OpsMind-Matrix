<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <SessionSidebar
      @new-chat="onNewChat"
      @select="onSelectSession"
    />

    <!-- 中间聊天区域 -->
    <div class="chat-main">
      <!-- 顶部导航（仅显示角色页签） -->
      <div class="chat-topbar">
        <button class="toggle-sidebar" @click="store.sidebarCollapsed = !store.sidebarCollapsed">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <div class="topbar-title">{{ currentSessionTitle }}</div>
        <div class="topbar-actions">
          <router-link v-if="store.userRole === 'engineer'" to="/engineer" class="nav-link">工作台</router-link>
          <router-link v-if="store.userRole === 'storekeeper'" to="/storekeeper" class="nav-link">库房</router-link>
          <router-link v-if="store.userRole === 'admin'" to="/admin" class="nav-link">管理</router-link>
        </div>
      </div>

      <!-- 聊天内容 -->
      <div class="chat-body">
        <!-- 空状态 -->
        <div v-if="store.messages.length === 0 && !isStreaming" class="empty-state">
          <div class="empty-logo">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="22" fill="#e8edfb" stroke="#4f6bed" stroke-width="2"/>
              <path d="M16 20 Q24 12 32 20" stroke="#4f6bed" stroke-width="2" fill="none"/>
              <circle cx="18" cy="18" r="2" fill="#4f6bed"/>
              <circle cx="30" cy="18" r="2" fill="#4f6bed"/>
              <path d="M20 28 Q24 32 28 28" stroke="#4f6bed" stroke-width="2" fill="none" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="empty-title">运维 AI 助手</div>
          <div class="empty-subtitle">输入您的问题，智能路由到合适的 Agent 处理</div>
          <div class="empty-hints">
            <div class="hint-chip" @click="sendQuick('帮我报修一台打印机，打印模糊')">报修打印机</div>
            <div class="hint-chip" v-if="store.userRole === 'storekeeper' || store.userRole === 'admin'" @click="sendQuick('查询库房中的耗材库存')">查询库存</div>
            <div class="hint-chip" @click="sendQuick('网络连接不上怎么办？')">网络故障</div>
            <div class="hint-chip" v-if="store.userRole !== 'storekeeper'" @click="sendQuick('查看我的工单状态')">工单状态</div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages" ref="messagesRef">
          <MessageBubble
            v-for="msg in store.messages"
            :key="msg.id"
            :role="msg.role"
            :content="msg.content"
            :sources="msg.sources"
            :msg-id="msg.id"
            @feedback="onFeedback"
          />
        </div>
      </div>

      <!-- 底部输入区 -->
      <div class="chat-footer">
        <ChatInput
          :disabled="isStreaming"
          @send="onSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import SessionSidebar from '../components/SessionSidebar.vue'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import { useChatStore } from '../stores/chat'
import { chatAPI } from '../api'

const router = useRouter()
const store = useChatStore()

const messagesRef = ref<HTMLElement>()
const isStreaming = ref(false)
let assistantMsgId = ''

onMounted(async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    router.push('/login')
    return
  }
  store.checkAuth()
  await store.loadSessions()
  if (store.sessions.length > 0) {
    await store.switchSession(store.sessions[0].id)
  } else {
    await store.ensureSession()
  }
})

const currentSessionTitle = computed(() => {
  const s = store.sessions.find(s => s.id === store.currentSessionId)
  return s?.title || '运维 AI 助手'
})

async function onNewChat() {
  store.clearMessages()
  store.currentSessionId = ''
  const id = await store.ensureSession()
  if (id) {
    store.currentSessionId = id
  }
}

async function onSelectSession(sessionId: string) {
  if (sessionId === store.currentSessionId) return
  await store.switchSession(sessionId)
}

async function onSend(text: string) {
  if (!store.currentSessionId) {
    const id = await store.ensureSession()
    if (!id) return
  }
  doSend(text)
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'msg_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10)
}

async function doSend(text: string) {
  const userMsgId = generateId()
  store.addMessage({ id: userMsgId, role: 'user', content: text, msg_type: 'text' })
  assistantMsgId = generateId()
  isStreaming.value = true
  // 流式消息也使用 MessageBubble 组件，初始显示"思考中..."
  store.addMessage({ id: assistantMsgId, role: 'assistant', content: '思考中...', msg_type: 'text' })
  let fullReply = ''
  let sources: Array<{ title: string; score: number }> = []

  try {
    for await (const event of chatAPI.streamMessage(store.currentSessionId, text)) {
      if (event.token) {
        fullReply += event.token
        store.addMessage({ id: assistantMsgId, role: 'assistant', content: fullReply, msg_type: 'text' })
      }
      if (event.sources) {
        sources = event.sources.map((s: string) => ({ title: s, score: 0.8 }))
      }
      if (event.done) {
        // 流式完成，替换为服务端真实消息 id（供赞/踩定位数据库记录）
        const realId = event.message_id != null ? String(event.message_id) : assistantMsgId
        const idx = store.messages.findIndex((m) => m.id === assistantMsgId)
        const finalMsg: any = {
          id: realId,
          role: 'assistant',
          content: fullReply,
          msg_type: 'text',
          sources,
        }
        if (idx !== -1) {
          store.messages[idx] = { ...store.messages[idx], ...finalMsg }
        } else {
          store.addMessage(finalMsg)
        }
        store.loadSessions()
      }
      if (event.error) {
        throw new Error(event.error)
      }
    }
  } catch (e: any) {
    const errMsg = e?.message || '服务暂时不可用'
    store.addMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: fullReply || `抱歉，${errMsg}，请稍后重试。`,
      msg_type: 'text',
    })
    console.error('Send message failed:', e)
  } finally {
    isStreaming.value = false
  }
}

function sendQuick(text: string) {
  onSend(text)
}

async function onFeedback(msgId: string, feedback: string) {
  try {
    const res = await chatAPI.sendFeedback(msgId, feedback)
    console.log('Feedback submitted:', res.data)
  } catch (e: any) {
    console.error('Feedback submission failed:', e?.message || e)
  }
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: #fff;
}

/* 主聊天区 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

/* 顶部栏 */
.chat-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  height: 48px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.toggle-sidebar {
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.1s;
}
.toggle-sidebar:hover {
  background: #f3f4f6;
  color: #374151;
}
.topbar-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topbar-actions {
  display: flex;
  gap: 8px;
}
.nav-link {
  font-size: 13px;
  color: #6b7280;
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
  transition: all 0.1s;
}
.nav-link:hover {
  background: #f3f4f6;
  color: #4f6bed;
}

/* 聊天主体 */
.chat-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.empty-logo {
  margin-bottom: 16px;
  opacity: 0.8;
}
.empty-title {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 8px;
}
.empty-subtitle {
  font-size: 14px;
  color: #9ca3af;
  margin-bottom: 24px;
}
.empty-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 480px;
}
.hint-chip {
  padding: 8px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
  background: #f9fafb;
}
.hint-chip:hover {
  border-color: #4f6bed;
  color: #4f6bed;
  background: #e8edfb;
}

/* 消息列表 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

/* 消息气泡（流式与普通共用） */
.messages .message-bubble {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  max-width: 800px;
}
.messages .message-bubble.user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.messages .message-bubble .avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
}
.messages .message-bubble.user .avatar {
  background: #4f6bed;
  color: #fff;
}
.messages .message-bubble .bubble {
  width: 100%;
  padding: 10px 16px;
  border-radius: 12px;
  background: #f3f4f6;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
}
.messages .message-bubble.user .bubble {
  background: #e8edfb;
}
.messages .message-bubble .content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 底部输入 */
.chat-footer {
  flex-shrink: 0;
  padding: 0 16px 16px;
}
</style>