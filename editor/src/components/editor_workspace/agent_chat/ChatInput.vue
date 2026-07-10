<!--
  Agent chat input.

  Usage:
  Emits a send event when the user presses Enter without Shift or clicks the
  send button. Supports optional quoted reference text displayed as a gray bar
  above the input area.
-->
<script setup lang="ts">
import { ref } from 'vue'
import { Globe, Send, X } from 'lucide-vue-next'

const props = defineProps<{
  disabled?: boolean
  centered?: boolean
  webSearchEnabled?: boolean
  reference?: string
}>()

const emit = defineEmits<{
  send: [text: string, reference?: string]
  'toggle-web-search': []
  'clear-reference': []
}>()

const text = ref('')

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed) {
    return
  }
  const reference = props.reference?.trim() || undefined
  emit('send', trimmed, reference)
  text.value = ''
  emit('clear-reference')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="chat-input-wrap" :class="{ centered }">
    <div class="input-container">
      <div v-if="reference" class="reference-bar">
        <span class="reference-text">{{ reference }}</span>
        <button class="reference-close" type="button" title="移除引用" @click="emit('clear-reference')">
          <X :size="13" />
        </button>
      </div>
      <textarea
        v-model="text"
        class="input-area"
        :class="{ 'has-reference': !!reference }"
        :disabled="disabled"
        placeholder="输入消息..."
        rows="1"
        @keydown="handleKeydown"
      ></textarea>
      <div class="input-toolbar">
        <div class="toolbar-left">
          <button
            class="web-search-toggle"
            :class="{ active: webSearchEnabled }"
            type="button"
            title="联网搜索"
            @click="emit('toggle-web-search')"
          >
            <Globe :size="14" />
          </button>
          <span class="input-hint">Enter send · Shift Enter newline</span>
        </div>
        <button class="send-btn" :disabled="disabled || !text.trim()" type="button" title="发送" @click="handleSend">
          <Send :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-input-wrap {
  position: absolute;
  left: 50%;
  z-index: 2;
  bottom: 16px;
  width: calc(100% - 32px);
  max-width: 500px;
  transform: translateX(-50%);
  transition:
    bottom 350ms cubic-bezier(0.4, 0, 0.2, 1),
    width 350ms cubic-bezier(0.4, 0, 0.2, 1);
}

.chat-input-wrap.centered {
  bottom: 50%;
  width: min(90%, 400px);
}

.input-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--input-border);
  border-radius: var(--radius-xl);
  background: var(--input-bg);
  backdrop-filter: blur(var(--blur-strength));
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.input-container:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-muted);
}

.reference-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 10px 0;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas-soft);
}

.reference-text {
  flex: 1;
  overflow: hidden;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reference-close {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: background 120ms, color 120ms;
}

.reference-close:hover {
  background: var(--color-surface-active);
  color: var(--color-text);
}

.input-area {
  width: 100%;
  min-height: 52px;
  max-height: 180px;
  padding: 14px 14px 0;
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  color: var(--input-text);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.input-area.has-reference {
  min-height: 24px;
  padding-top: 8px;
}

.input-area::placeholder {
  color: var(--input-placeholder);
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 38px;
  padding: 0 10px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.web-search-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid #38bdf8;
  border-radius: 50%;
  background: transparent;
  color: #38bdf8;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast);
}

.web-search-toggle.active {
  border-color: #38bdf8;
  color: #fff;
  background: #38bdf8;
}

.web-search-toggle:hover {
  border-color: #7dd3fc;
  color: #7dd3fc;
}

.input-hint {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 9px;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--input-btn-bg);
  color: var(--input-send-disabled);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent);
  color: #0a0a0a;
}

.send-btn:disabled {
  cursor: default;
  opacity: 0.35;
}
</style>
