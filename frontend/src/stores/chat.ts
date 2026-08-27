import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, ChatSession } from '../types'
import { chatAPI } from '../api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('')
  const currentAgent = ref<string>('ops-agent')
  const isAuthenticated = ref(false)
  const userRole = ref<string>('')
  const username = ref<string>('')
  const sessionsLoaded = ref(false)
  const sidebarCollapsed = ref(false)

  // 别名，兼容旧代码
  const sessionId = computed(() => currentSessionId.value)

  const setAuth = (token: string, role: string, name: string) => {
    localStorage.setItem('token', token)
    localStorage.setItem('role', role)
    localStorage.setItem('username', name)
    isAuthenticated.value = true
    userRole.value = role
    username.value = name
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    isAuthenticated.value = false
    userRole.value = ''
    username.value = ''
    messages.value = []
    sessions.value = []
    currentSessionId.value = ''
    sessionsLoaded.value = false
  }

  const checkAuth = () => {
    const token = localStorage.getItem('token')
    if (token) {
      isAuthenticated.value = true
      const storedRole = localStorage.getItem('role')
      const storedName = localStorage.getItem('username')
      if (storedRole) userRole.value = storedRole
      if (storedName) username.value = storedName
    }
  }

  const addMessage = (msg: ChatMessage) => {
    const idx = messages.value.findIndex((m) => m.id === msg.id)
    if (idx !== -1) {
      // 替换整个对象以触发 Vue 响应式更新
      messages.value[idx] = { ...messages.value[idx], ...msg }
    } else {
      messages.value.push(msg)
    }
  }

  const clearMessages = () => {
    messages.value = []
  }

  // 会话管理
  const loadSessions = async () => {
    try {
      const res = await chatAPI.listSessions()
      sessions.value = res.data.sessions || []
      sessionsLoaded.value = true
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }

  const createSession = async (): Promise<string> => {
    try {
      const res = await chatAPI.createSession()
      const session = res.data
      sessions.value.unshift(session)
      return session.id
    } catch (e) {
      console.error('Failed to create session:', e)
      return ''
    }
  }

  const ensureSession = async (): Promise<string> => {
    if (currentSessionId.value) return currentSessionId.value
    const id = await createSession()
    if (id) {
      currentSessionId.value = id
    }
    return id
  }

  const switchSession = async (sessionId: string) => {
    currentSessionId.value = sessionId
    messages.value = []
    try {
      const res = await chatAPI.getSessionMessages(sessionId)
      const msgs = res.data.messages || []
      messages.value = msgs.map((m: any) => ({
        id: String(m.id),
        role: m.role,
        content: m.content,
        msg_type: m.msg_type || 'text',
        sources: m.sources ? JSON.parse(m.sources) : [],
        created_at: m.created_at,
      }))
    } catch (e) {
      console.error('Failed to load session messages:', e)
    }
  }

  const deleteSession = async (sessionId: string) => {
    try {
      await chatAPI.deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = ''
        messages.value = []
      }
    } catch (e) {
      console.error('Failed to delete session:', e)
    }
  }

  const updateSessionInList = (sessionId: string, title: string) => {
    const s = sessions.value.find(s => s.id === sessionId)
    if (s) {
      s.title = title
      s.updated_at = new Date().toISOString()
    }
  }

  return {
    messages, sessions, currentSessionId, sessionId, currentAgent,
    isAuthenticated, userRole, username, sessionsLoaded, sidebarCollapsed,
    addMessage, clearMessages, setAuth, logout, checkAuth,
    loadSessions, createSession, ensureSession, switchSession, deleteSession,
    updateSessionInList,
  }
})