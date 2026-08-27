<template>
  <div :class="['message-bubble', role]">
    <div class="avatar">
      <template v-if="role === 'user'">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v1.2c0 .66.54 1.2 1.2 1.2h16.8c.66 0 1.2-.54 1.2-1.2v-1.2c0-3.2-6.4-4.8-9.6-4.8z"/>
        </svg>
      </template>
      <template v-else>
        <svg width="16" height="16" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="22" fill="#4f6bed" stroke="#4f6bed" stroke-width="2"/>
          <path d="M16 20 Q24 12 32 20" stroke="#fff" stroke-width="2" fill="none"/>
          <circle cx="18" cy="18" r="2" fill="#fff"/>
          <circle cx="30" cy="18" r="2" fill="#fff"/>
        </svg>
      </template>
    </div>
    <div class="bubble">
      <div class="content" v-text="content" />
      <div v-if="sources && sources.length > 0" class="sources">
        <span class="source-item" v-for="s in sources" :key="s.title">{{ s.title }}</span>
      </div>
      <div v-if="role === 'assistant' && msgId" class="feedback">
        <button class="feedback-btn" @click="$emit('feedback', msgId, 'helpful')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
        </button>
        <button class="feedback-btn" @click="$emit('feedback', msgId, 'unhelpful')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  role: string;
  content: string;
  sources?: Array<{ title: string; score: number }>;
  msgId?: string;
}>();

defineEmits<{
  feedback: [messageId: string, feedback: string];
}>();
</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  max-width: 800px;
}
.message-bubble.user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message-bubble.user .avatar {
  background: #4f6bed;
  color: #fff;
}

.bubble {
  width: 100%;
  padding: 10px 16px;
  border-radius: 12px;
  background: #f3f4f6;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
}
.message-bubble.user .bubble {
  background: #e8edfb;
  color: #1f2937;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.sources {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.source-item {
  font-size: 11px;
  color: #9ca3af;
  background: #e5e7eb;
  padding: 2px 8px;
  border-radius: 10px;
}

.feedback {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #e5e7eb;
}
.feedback-btn {
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px 8px;
  display: flex;
  align-items: center;
  transition: all 0.1s;
}
.feedback-btn:hover {
  color: #4f6bed;
  border-color: #4f6bed;
  background: #e8edfb;
}
</style>