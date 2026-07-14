<!--
  Agent chat input.

  Usage:
  Emits a send event when the user presses Enter without Shift or clicks the
  send button. Supports optional quoted reference text displayed as a gray bar
  above the input area.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { BrainCircuit, Check, ChevronDown, Globe, Send, X } from 'lucide-vue-next'
import type { AgentLoopMode } from '@/api/agent'

const props = defineProps<{
  disabled?: boolean
  centered?: boolean
  webSearchEnabled?: boolean
  agentMode?: AgentLoopMode
  reference?: string
}>()

const emit = defineEmits<{
  send: [text: string, reference?: string]
  'toggle-web-search': []
  'set-agent-mode': [mode: AgentLoopMode]
  'clear-reference': []
}>()

const text = ref('')
const loopModeMenu = ref<HTMLDetailsElement | null>(null)

const loopModeOptions: Array<{ value: AgentLoopMode; label: string; hint: string }> = [
  { value: 'auto', label: 'Auto', hint: '自动选择' },
  { value: 'simple', label: 'Simple', hint: '直接回答' },
  { value: 'react', label: 'ReAct', hint: '工具循环' },
  { value: 'plan', label: 'Plan', hint: '规划执行' },
]

const selectedLoopMode = computed<AgentLoopMode>(() => props.agentMode || 'auto')
const selectedLoopModeLabel = computed(() => {
  return loopModeOptions.find((option) => option.value === selectedLoopMode.value)?.label || 'Auto'
})

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

function handleLoopModeSummaryClick(event: MouseEvent) {
  if (props.disabled) {
    event.preventDefault()
  }
}

function selectLoopMode(mode: AgentLoopMode) {
  emit('set-agent-mode', mode)
  if (loopModeMenu.value) {
    loopModeMenu.value.open = false
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
        <details ref="loopModeMenu" class="loop-mode-dropdown" :class="{ disabled }">
          <summary
            class="loop-mode-trigger"
            title="Agent Loop 模式"
            aria-label="Agent Loop 模式"
            @click="handleLoopModeSummaryClick"
          >
            <BrainCircuit :size="13" />
            <span class="loop-mode-label">{{ selectedLoopModeLabel }}</span>
            <ChevronDown :size="12" class="loop-mode-caret" />
          </summary>
          <div class="loop-mode-menu" role="listbox" aria-label="Agent Loop 模式">
            <button
              v-for="option in loopModeOptions"
              :key="option.value"
              class="loop-mode-option"
              :class="{ active: selectedLoopMode === option.value }"
              type="button"
              role="option"
              :aria-selected="selectedLoopMode === option.value"
              @click="selectLoopMode(option.value)"
            >
              <span class="loop-mode-option-label">{{ option.label }}</span>
              <span class="loop-mode-option-hint">{{ option.hint }}</span>
              <Check v-if="selectedLoopMode === option.value" :size="13" class="loop-mode-check" />
            </button>
          </div>
        </details>
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
  overflow: visible;
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
  min-width: 0;
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

.loop-mode-dropdown {
  position: relative;
  margin-left: auto;
}

.loop-mode-dropdown.disabled {
  pointer-events: none;
  opacity: 0.55;
}

.loop-mode-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 26px;
  padding: 0 6px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-muted, #8b93a7);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1;
  list-style: none;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.loop-mode-trigger::-webkit-details-marker {
  display: none;
}

.loop-mode-trigger::marker {
  content: '';
}

.loop-mode-trigger:hover,
.loop-mode-dropdown[open] .loop-mode-trigger {
  background: transparent;
  color: var(--color-text-secondary, #a8b0c1);
}

.loop-mode-label {
  min-width: 36px;
  color: inherit;
}

.loop-mode-caret {
  color: inherit;
  transition: transform 120ms ease;
}

.loop-mode-dropdown[open] .loop-mode-caret {
  transform: rotate(180deg);
}

.loop-mode-menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: 198px;
  padding: 4px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 10px;
  background: var(--color-surface, #111827);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
}

.loop-mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 34px;
  padding: 6px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--color-text-secondary, #a8b0c1);
  font-family: var(--font-mono);
  text-align: left;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.loop-mode-option:hover,
.loop-mode-option.active {
  background: rgba(66, 36, 235, 0.14);
  color: var(--color-text, #e5e7eb);
}

.loop-mode-option-label {
  color: inherit;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.02em;
}

.loop-mode-option-hint {
  margin-left: auto;
  color: var(--color-text-tertiary, #7c8496);
  font-size: 10px;
  line-height: 1.2;
  white-space: nowrap;
}

.loop-mode-check {
  flex-shrink: 0;
  color: var(--color-accent, #4224eb);
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
