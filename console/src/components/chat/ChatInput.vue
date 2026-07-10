<!--
  聊天输入框 — 液态玻璃风格,跟随主题切换。
-->

<script setup>
import { ref } from 'vue'
import { Send, Paperclip, Globe } from 'lucide-vue-next'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const text = ref('')

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed || props.disabled) return
  emit('send', trimmed)
  text.value = ''
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="chat-input-wrap">
    <div class="input-container">
      <textarea
        v-model="text"
        class="input-area"
        :disabled="disabled"
        placeholder="输入消息..."
        rows="1"
        @keydown="onKeydown"
      ></textarea>

      <div class="input-toolbar">
        <!-- 左侧按钮组 -->
        <div class="left-btns">
          <label class="tool-btn" title="上传文件">
            <input class="hidden-input" type="file" disabled />
            <Paperclip :size="15" />
          </label>
          <button class="tool-btn search-btn" title="联网搜索" type="button">
            <Globe :size="14" />
            <span class="search-label">Search</span>
          </button>
        </div>

        <button
          class="send-btn"
          :disabled="disabled || !text.trim()"
          @click="handleSend"
          title="发送"
        >
          <Send :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-input-wrap {
  padding: var(--space-12) var(--space-16) var(--space-16);
  flex-shrink: 0;
}

.input-container {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-xl);
  overflow: hidden;
  border: 1px solid var(--input-border);
  background: var(--input-bg);
  backdrop-filter: blur(var(--blur-strength));
  -webkit-backdrop-filter: blur(var(--blur-strength));
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.input-container:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-muted);
}

.input-area {
  width: 100%;
  min-height: 52px;
  max-height: 200px;
  padding: 14px 14px 0;
  border: none;
  background: transparent;
  color: var(--input-text);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.5;
  outline: none;
  resize: none;
}

.input-area::placeholder {
  color: var(--input-placeholder);
}

.input-area:disabled {
  opacity: 0.4;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 10px;
}

.left-btns {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--input-btn-bg);
  color: var(--input-btn-color);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-btn:hover {
  background: var(--input-btn-hover-bg);
  color: var(--input-btn-hover-color);
}

.hidden-input {
  display: none;
}

.search-btn {
  width: auto;
  padding: 0 12px;
  gap: 6px;
  border: 1px solid rgba(0, 183, 215, 0.3);
  border-radius: 18px;
  background: rgba(0, 183, 215, 0.1);
  color: var(--color-sky);
}

.search-btn:hover {
  background: rgba(0, 183, 215, 0.18);
  border-color: rgba(0, 183, 215, 0.5);
}

.search-label {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--input-btn-bg);
  color: var(--input-send-disabled);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent);
  color: #0a0a0a;
}

.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
