import { ref, onUnmounted } from 'vue'

interface WSMessage {
  type: string;
  payload: Record<string, unknown>;
}

export function useWebSocket(initialSessionId: string = '') {
  const connected = ref(false)
  const replyContent = ref('')
  const replyIntent = ref('')
  const replyConfidence = ref(0)
  const replySources = ref<Array<{ title: string; score: number }>>([])
  const isStreaming = ref(false)
  const thinkingMessage = ref('')
  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let currentSessionId = initialSessionId

  function connect(sessionId?: string) {
    disconnect()

    if (sessionId !== undefined) {
      currentSessionId = sessionId
    }

    const sid = currentSessionId
    if (!sid) {
      console.warn('[WebSocket] No sessionId, skip connect')
      return
    }

    const token = localStorage.getItem('token')
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}/ws/chat/${sid}?token=${token}`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data)
      switch (msg.type) {
        case 'reply_start':
          replyContent.value = ''
          replyIntent.value = (msg.payload.intent as string) || ''
          isStreaming.value = true
          thinkingMessage.value = ''
          break
        case 'reply_chunk':
          replyContent.value += msg.payload.content || ''
          break
        case 'reply_end':
          isStreaming.value = false
          replyConfidence.value = (msg.payload.confidence as number) || 0
          replySources.value = (msg.payload.sources as Array<{ title: string; score: number }>) || []
          break
        case 'ticket_preview':
          break
        case 'thinking':
          thinkingMessage.value = (msg.payload.message as string) || ''
          break
      }
    }

    ws.onerror = () => {
      console.warn('[WebSocket] 连接异常，将自动重连')
    }

    ws.onclose = () => {
      connected.value = false
      scheduleReconnect()
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
      ws.send(JSON.stringify({ type: 'message', payload: { content, msg_type: 'text' } }))
    } else {
      console.warn('[WebSocket] 未连接，消息发送失败')
    }
  }

  function sendFeedback(messageId: string, feedback: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'feedback', payload: { message_id: messageId, feedback } }))
    } else {
      console.warn('[WebSocket] 未连接，反馈发送失败')
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null  // 防止触发重连
      ws.close()
      ws = null
    }
    connected.value = false
    isStreaming.value = false
    replyContent.value = ''
  }

  onUnmounted(disconnect)

  return {
    connected,
    replyContent,
    replyIntent,
    replyConfidence,
    replySources,
    isStreaming,
    thinkingMessage,
    connect,
    sendMessage,
    sendFeedback,
    disconnect,
  }
}