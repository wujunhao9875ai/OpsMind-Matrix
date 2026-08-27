/**
 * 统一 WebSocket 连接 (Unified WebSocket)
 * 用于 Multi-Agent 架构中前端与 Orchestrator 的通信
 * 
 * 职责：
 * - 维护与 Orchestrator 的单一 WebSocket 连接
 * - 支持多 Agent 消息路由（ops / dispatch / warehouse）
 * - 流式消息推送和状态管理
 * - 自动重连和会话恢复
 */
import { ref, onUnmounted } from 'vue'

interface WSMessage {
  type: string
  payload: Record<string, unknown>
  trace_id?: string
}

interface AgentMessage {
  agent: string
  type: string
  content: string
  trace_id?: string
}

export function useUnifiedWebSocket(sessionId: string = '') {
  const connected = ref(false)
  const isStreaming = ref(false)
  const currentAgent = ref<string>('')
  const thinkingMessage = ref('')
  const traceId = ref('')

  // 各 Agent 的回复内容
  const opsReply = ref('')
  const dispatchReply = ref('')
  const warehouseReply = ref('')

  // 聚合回复（全量）
  const replyContent = ref('')
  const replySources = ref<Array<{ title: string; score: number }>>([])

  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let _currentSessionId = sessionId

  function connect(newSessionId?: string) {
    disconnect()

    if (newSessionId !== undefined) {
      _currentSessionId = newSessionId
    }

    if (!_currentSessionId) {
      console.warn('[UnifiedWS] No sessionId, skip connect')
      return
    }

    const token = localStorage.getItem('token')
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}/ws/chat/${_currentSessionId}?token=${token}`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      console.log('[UnifiedWS] Connected to Orchestrator')
    }

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data)
      traceId.value = (msg.trace_id as string) || ''

      switch (msg.type) {
        case 'intent_routed':
          // Orchestrator 告知当前路由到的 Agent
          currentAgent.value = (msg.payload.agent as string) || ''
          break

        case 'reply_start':
          replyContent.value = ''
          isStreaming.value = true
          thinkingMessage.value = ''
          break

        case 'reply_chunk':
          replyContent.value += (msg.payload.content as string) || ''
          break

        case 'reply_end':
          isStreaming.value = false
          replySources.value = (msg.payload.sources as Array<{ title: string; score: number }>) || []
          break

        case 'agent_message':
          // 多 Agent 编排消息
          handleAgentMessage(msg.payload as unknown as AgentMessage)
          break

        case 'thinking':
          thinkingMessage.value = (msg.payload.message as string) || ''
          break

        case 'error':
          console.error('[UnifiedWS] Error:', msg.payload.message)
          break
      }
    }

    ws.onerror = () => {
      console.warn('[UnifiedWS] Connection error, will auto-reconnect')
    }

    ws.onclose = () => {
      connected.value = false
      scheduleReconnect()
    }
  }

  function handleAgentMessage(msg: AgentMessage) {
    switch (msg.agent) {
      case 'ops-agent':
        opsReply.value += msg.content || ''
        break
      case 'dispatch-agent':
        dispatchReply.value += msg.content || ''
        break
      case 'warehouse-agent':
        warehouseReply.value += msg.content || ''
        break
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect()
    }, 3000)
  }

  function sendMessage(content: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'message',
        payload: { content, msg_type: 'text' },
      }))
    } else {
      console.warn('[UnifiedWS] Not connected, message send failed')
    }
  }

  function sendFeedback(messageId: string, feedback: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'feedback',
        payload: { message_id: messageId, feedback },
      }))
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    connected.value = false
    isStreaming.value = false
    replyContent.value = ''
    currentAgent.value = ''
    opsReply.value = ''
    dispatchReply.value = ''
    warehouseReply.value = ''
  }

  onUnmounted(disconnect)

  return {
    connected,
    isStreaming,
    currentAgent,
    thinkingMessage,
    traceId,
    replyContent,
    replySources,
    opsReply,
    dispatchReply,
    warehouseReply,
    connect,
    sendMessage,
    sendFeedback,
    disconnect,
  }
}