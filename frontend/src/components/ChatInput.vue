<template>
  <div class="chat-input-wrapper">
    <div class="input-container">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-textarea"
        :placeholder="placeholder"
        :disabled="disabled"
        @keydown.enter.exact="handleEnter"
        @input="autoResize"
        rows="1"
      />
      <div class="input-actions">
        <div class="input-toggles"></div>
        <button
          class="send-btn"
          :class="{ active: canSend }"
          :disabled="!canSend || disabled"
          @click="send"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="input-footer">
      <span class="footer-text">运维 AI 助手 · 智能路由到合适的 Agent</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from "vue";

const props = defineProps<{
  disabled?: boolean;
  placeholder?: string;
}>();

const emit = defineEmits<{ send: [text: string] }>();
const text = ref("");
const textareaRef = ref<HTMLTextAreaElement>();

const canSend = computed(() => text.value.trim().length > 0);

function autoResize() {
  nextTick(() => {
    const el = textareaRef.value;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  });
}

function handleEnter(e: KeyboardEvent) {
  if (e.shiftKey) return; // Shift+Enter 换行
  e.preventDefault();
  send();
}

function send() {
  if (!text.value.trim() || props.disabled) return;
  emit("send", text.value.trim());
  text.value = "";
  nextTick(autoResize);
}
</script>

<style scoped>
.chat-input-wrapper {
  max-width: 800px;
  margin: 0 auto;
}

.input-container {
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  padding: 8px 12px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-container:focus-within {
  border-color: #4f6bed;
  box-shadow: 0 0 0 3px rgba(79, 107, 237, 0.1);
}

.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  color: #1f2937;
  background: transparent;
  padding: 4px 0;
  font-family: inherit;
  min-height: 24px;
  max-height: 200px;
}
.input-textarea::placeholder {
  color: #9ca3af;
}
.input-textarea:disabled {
  opacity: 0.6;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}

.input-toggles {
  display: flex;
  gap: 8px;
}

.send-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #e5e7eb;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
.send-btn.active {
  background: #4f6bed;
  color: #fff;
}
.send-btn.active:hover {
  background: #3b57d9;
}
.send-btn:disabled {
  cursor: not-allowed;
}

.input-footer {
  text-align: center;
  padding: 8px 0 0;
}
.footer-text {
  font-size: 11px;
  color: #c5c9d2;
}
</style>