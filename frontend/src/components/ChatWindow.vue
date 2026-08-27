<template>
  <div class="chat-window">
    <div class="messages" ref="messagesRef">
      <MessageBubble
        v-for="msg in messages"
        :key="msg.id"
        :role="msg.role"
        :content="msg.content"
        :sources="msg.sources"
        :msg-id="msg.id"
        @feedback="onFeedback"
      />
      <div v-if="thinkingMessage" class="thinking-banner">
        <span class="thinking-dot" />
        <span>{{ thinkingMessage }}</span>
      </div>
      <div v-if="streaming" class="message-bubble assistant">
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="content">{{ streamingContent }}</div>
        </div>
      </div>
    </div>
    <ChatInput :disabled="streaming" @send="onSend" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import MessageBubble from "./MessageBubble.vue";
import ChatInput from "./ChatInput.vue";
import type { ChatMessage } from "../types";

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  streamingContent: string;
  thinkingMessage: string;
}>();

const emit = defineEmits<{
  send: [text: string];
  feedback: [messageId: string, feedback: string];
}>();

const messagesRef = ref<HTMLElement>();

watch(
  () => [props.messages.length, props.streamingContent],
  () => nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }),
);

function onSend(text: string) { emit("send", text); }
function onFeedback(msgId: string, feedback: string) { emit("feedback", msgId, feedback); }
</script>

<style scoped>
.chat-window { display: flex; flex-direction: column; height: 100%; }
.messages { flex: 1; overflow-y: auto; padding: 16px; }
.thinking-banner { display: flex; align-items: center; gap: 8px; padding: 8px 16px; margin: 4px 0; background: #f0f7ff; border-radius: 8px; font-size: 13px; color: #409eff; }
.thinking-dot { width: 8px; height: 8px; border-radius: 50%; background: #409eff; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
</style>