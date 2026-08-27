import axios from 'axios'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export { api }

export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
}

export const chatAPI = {
  getWebSocketUrl: (sessionId: string) => {
    const token = localStorage.getItem('token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/chat/${sessionId}?token=${token}`
  },

  // 发送消息并获取回复（REST API，非流式）
  sendMessage: (sessionId: string, content: string, msgType: string = 'text') =>
    api.post(`/chat/sessions/${sessionId}/messages`, { content, msg_type: msgType }),

  // SSE 流式发送消息并获取回复
  streamMessage: async function* (sessionId: string, content: string) {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content, msg_type: 'text' }),
    })

    if (!response.ok) {
      const err = await response.text()
      throw new Error(`HTTP ${response.status}: ${err}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6))
          } catch {
            // skip malformed
          }
        }
      }
    }
  },

  // 消息反馈（赞/踩，踩时自动上报 badcase）
  sendFeedback: (messageId: string, feedback: string) =>
    api.post(`/chat/messages/${messageId}/feedback`, { feedback }),

  // 会话管理
  listSessions: () => api.get('/chat/sessions'),
  createSession: (title?: string) => api.post('/chat/sessions', { title: title || '新对话' }),
  getSession: (id: string) => api.get(`/chat/sessions/${id}`),
  getSessionMessages: (id: string) => api.get(`/chat/sessions/${id}/messages`),
  deleteSession: (id: string) => api.delete(`/chat/sessions/${id}`),
  updateSessionTitle: (id: string, title: string) => api.put(`/chat/sessions/${id}/title`, { title }),
}

export const adminAPI = {
  getTickets: (params: any) => api.get('/dispatch/tickets', { params }),
  getEngineers: () => api.get('/dispatch/engineers'),
  assignTicket: (ticketId: string, engineerId?: string) =>
    api.post('/dispatch/assign', { ticket_id: ticketId, engineer_id: engineerId }),
  resolveTicket: (ticketId: string, resolution: string) =>
    api.post('/dispatch/resolve', { ticket_id: ticketId, resolution }),
  cancelTicket: (ticketId: string, reason: string) =>
    api.post('/dispatch/cancel', { ticket_id: ticketId, reason }),
  reassignTicket: (ticketId: string, engineerId: string, reason?: string) =>
    api.post('/dispatch/reassign', { ticket_id: ticketId, engineer_id: engineerId, reason }),
  urgeTicket: (ticketId: string) =>
    api.post('/dispatch/urge', { ticket_id: ticketId }),
  getStats: () => api.get('/dispatch/stats'),
  createTicket: (data: any) => api.post('/dispatch/tickets', data),
  closeTicket: (ticketId: string) => api.post('/dispatch/close', { ticket_id: ticketId }),
  reopenTicket: (ticketId: string, reason?: string) =>
    api.post('/dispatch/reopen', { ticket_id: ticketId, reason }),
  changePriority: (ticketId: string, urgency: string) =>
    api.post('/dispatch/priority', { ticket_id: ticketId, urgency }),
  createEngineer: (data: any) => api.post('/dispatch/engineers', data),
  acceptTicket: (ticketId: string) => api.post('/dispatch/accept', { ticket_id: ticketId }),
  rejectTicket: (ticketId: string, reason?: string) =>
    api.post('/dispatch/reject', { ticket_id: ticketId, reason }),
}

export const warehouseAPI = {
  getDevices: (params: any) => api.get('/warehouse/devices', { params }),
  getDevice: (id: string) => api.get(`/warehouse/devices/${id}`),
  createDevice: (data: any) => api.post('/warehouse/devices', data),
  deviceStatusChange: (id: string, data: any) => api.put(`/warehouse/devices/${id}/status`, data),
  transferDevice: (id: string, data: any) => api.put(`/warehouse/devices/${id}/transfer`, data),
  getDeviceLogs: (id: string) => api.get(`/warehouse/devices/${id}/logs`),
  getInventory: (params: any) => api.get('/warehouse/inventory', { params }),
  getInventoryItem: (id: string) => api.get(`/warehouse/inventory/${id}`),
  createInventory: (data: any) => api.post('/warehouse/inventory', data),
  stockIn: (id: string, data: any) => api.post(`/warehouse/inventory/${id}/stock-in`, data),
  stockOut: (id: string, data: any) => api.post(`/warehouse/inventory/${id}/stock-out`, data),
  getInventoryTransactions: (id: string, params?: any) => api.get(`/warehouse/inventory/${id}/transactions`, { params }),
  getSpareRequests: (params: any) => api.get('/warehouse/spare-requests', { params }),
  approveSpareRequest: (id: string) => api.put(`/warehouse/spare-requests/${id}/approve`),
  rejectSpareRequest: (id: string, reason: string) =>
    api.put(`/warehouse/spare-requests/${id}/reject`, null, { params: { reason } }),
  fulfillSpareRequest: (id: string) => api.put(`/warehouse/spare-requests/${id}/fulfill`),
  getLocations: () => api.get('/warehouse/locations'),
  createLocation: (data: any) => api.post('/warehouse/locations', data),
  updateLocation: (id: string, data: any) => api.put(`/warehouse/locations/${id}`, data),
  deleteLocation: (id: string) => api.delete(`/warehouse/locations/${id}`),
  getStats: () => api.get('/warehouse/stats/overview'),
  ocrRecognize: (image: File) => {
    const formData = new FormData()
    formData.append('image', image)
    return api.post('/warehouse/ocr/recognize', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export default api