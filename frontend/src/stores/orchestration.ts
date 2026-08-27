/**
 * 前端编排状态 (Orchestration State)
 * 用于 Multi-Agent 架构中前端的状态管理
 * 
 * 职责：
 * - 当前路由的 Agent 状态
 * - 跨 Agent 编排的进度追踪
 * - 多 Agent 回复的聚合展示
 */
import { ref, computed } from 'vue'

export interface AgentState {
  name: string
  status: 'idle' | 'thinking' | 'streaming' | 'done' | 'error'
  reply: string
  error?: string
}

export interface OrchestrationProgress {
  step: number
  totalSteps: number
  description: string
}

export function useOrchestration() {
  // 当前激活的 Agent
  const activeAgent = ref<string>('')

  // 各 Agent 状态
  const agents = ref<Record<string, AgentState>>({
    'ops-agent': { name: 'ops-agent', status: 'idle', reply: '' },
    'dispatch-agent': { name: 'dispatch-agent', status: 'idle', reply: '' },
    'warehouse-agent': { name: 'warehouse-agent', status: 'idle', reply: '' },
  })

  // 编排进度
  const progress = ref<OrchestrationProgress | null>(null)

  // 是否正在进行跨 Agent 编排
  const isOrchestrating = computed(() => progress.value !== null)

  // 聚合所有 Agent 的回复
  const aggregatedReply = computed(() => {
    return Object.values(agents.value)
      .filter(a => a.reply)
      .map(a => `[${a.name}] ${a.reply}`)
      .join('\n')
  })

  function setAgentStatus(agentName: string, status: AgentState['status']) {
    if (agents.value[agentName]) {
      agents.value[agentName].status = status
    }
  }

  function appendAgentReply(agentName: string, content: string) {
    if (agents.value[agentName]) {
      agents.value[agentName].reply += content
    }
  }

  function setAgentError(agentName: string, error: string) {
    if (agents.value[agentName]) {
      agents.value[agentName].status = 'error'
      agents.value[agentName].error = error
    }
  }

  function startOrchestration(steps: number, description: string) {
    progress.value = { step: 0, totalSteps: steps, description }
  }

  function advanceProgress(description?: string) {
    if (progress.value) {
      progress.value.step++
      if (description) {
        progress.value.description = description
      }
    }
  }

  function completeOrchestration() {
    progress.value = null
  }

  function reset() {
    activeAgent.value = ''
    progress.value = null
    Object.keys(agents.value).forEach(key => {
      agents.value[key] = { name: key, status: 'idle', reply: '' }
    })
  }

  return {
    activeAgent,
    agents,
    progress,
    isOrchestrating,
    aggregatedReply,
    setAgentStatus,
    appendAgentReply,
    setAgentError,
    startOrchestration,
    advanceProgress,
    completeOrchestration,
    reset,
  }
}