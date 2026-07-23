<!--
  Agent chat input.

  Usage:
  Emits a send event when the user presses Enter without Shift or clicks the
  send button. Supports optional quoted reference text displayed as a gray bar
  above the input area.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Check, ChevronDown, Globe, Plus, Send, Settings, Shield, X } from 'lucide-vue-next'
import AttachmentBlocks from '@/components/editor_workspace/agent_chat/AttachmentBlocks.vue'
import type { AgentAccessMode } from '@/api/agent'
import type { AgentUploadedAttachment } from '@/stores/chat'

const props = defineProps<{
  disabled?: boolean
  centered?: boolean
  webSearchEnabled?: boolean
  modelLabel?: string
  agentAccessMode?: AgentAccessMode
  reference?: string
  attachments?: AgentUploadedAttachment[]
  suggestions?: string[]
  suggestionsLoading?: boolean
}>()

const emit = defineEmits<{
  send: [text: string, reference?: string]
  'toggle-web-search': []
  'configure-model': []
  'set-agent-access-mode': [mode: AgentAccessMode]
  'clear-reference': []
  'remove-attachment': [attachment: AgentUploadedAttachment]
  'file-select': [file: File]
  'select-suggestion': [suggestion: string]
}>()

const text = ref('')
const accessModeMenu = ref<HTMLDetailsElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const accessModeOptions: Array<{ value: AgentAccessMode; label: string; hint: string }> = [
  { value: 'readonly', label: '只读', hint: '全目录只读' },
  { value: 'sandbox', label: '沙盒', hint: '知识库内写' },
  { value: 'full_access', label: '完全访问', hint: '不限制边界' },
]

const selectedAccessMode = computed<AgentAccessMode>(() => props.agentAccessMode || 'sandbox')
const selectedAccessModeLabel = computed(() => {
  return accessModeOptions.find((option) => option.value === selectedAccessMode.value)?.label || '沙盒'
})
const displayedModelLabel = computed(() => props.modelLabel?.trim() || '配置模型')

function adjustHeight() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  const max = 6 * Math.round(parseFloat(getComputedStyle(el).lineHeight)) + 14
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
}

watch(text, () => nextTick(adjustHeight))

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

function handleAccessModeSummaryClick(event: MouseEvent) {
  if (props.disabled) {
    event.preventDefault()
  }
}

function selectAccessMode(mode: AgentAccessMode) {
  emit('set-agent-access-mode', mode)
  if (accessModeMenu.value) {
    accessModeMenu.value.open = false
  }
}

function triggerFilePicker() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    emit('file-select', file)
  }
  input.value = ''
}
</script>

<template>
  <div class="chat-input-wrap" :class="{ centered }">
    <div v-if="!centered && !attachments?.length && suggestions?.length" class="task-suggestions">
      <button
        v-for="suggestion in suggestions"
        :key="suggestion"
        class="suggestion-button"
        type="button"
        :disabled="disabled"
        @click="emit('select-suggestion', suggestion)"
      >
        {{ suggestion }}
      </button>
    </div>
    <AttachmentBlocks
      v-if="!centered && attachments?.length"
      class="input-attachments"
      :attachments="attachments"
      align="left"
      @remove="emit('remove-attachment', $event)"
    />
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
        ref="textareaRef"
        placeholder="输入消息..."
        rows="1"
        @keydown="handleKeydown"
      ></textarea>
      <div class="input-toolbar">
        <div class="toolbar-left">
          <button
            class="attach-file-btn"
            type="button"
            title="上传文件"
            :disabled="disabled"
            @click="triggerFilePicker"
          >
            <Plus :size="14" />
          </button>
          <input
            ref="fileInput"
            type="file"
            class="file-input-hidden"
            @change="handleFileChange"
          />
          <button
            class="web-search-toggle"
            :class="{ active: webSearchEnabled }"
            type="button"
            title="联网搜索"
            :disabled="disabled"
            @click="emit('toggle-web-search')"
          >
            <Globe :size="14" />
          </button>
          <details ref="accessModeMenu" class="access-mode-dropdown" :class="{ disabled }">
            <summary
              class="access-mode-trigger"
              title="Agent 权限"
              aria-label="Agent 权限"
              @click="handleAccessModeSummaryClick"
            >
              <Shield :size="12" />
              <span class="access-mode-label">{{ selectedAccessModeLabel }}</span>
              <ChevronDown :size="11" class="access-mode-caret" />
            </summary>
            <div class="access-mode-menu" role="listbox" aria-label="Agent 权限">
              <button
                v-for="option in accessModeOptions"
                :key="option.value"
                class="access-mode-option"
                :class="{ active: selectedAccessMode === option.value }"
                type="button"
                role="option"
                :aria-selected="selectedAccessMode === option.value"
                @click="selectAccessMode(option.value)"
              >
                <span class="access-mode-option-label">{{ option.label }}</span>
                <span class="access-mode-option-hint">{{ option.hint }}</span>
                <Check v-if="selectedAccessMode === option.value" :size="13" class="access-mode-check" />
              </button>
            </div>
          </details>
        </div>
        <button
          class="model-config-trigger"
          type="button"
          :disabled="disabled"
          title="配置模型"
          @click="emit('configure-model')"
        >
          <Settings :size="13" />
          <span>{{ displayedModelLabel }}</span>
        </button>
        <button class="send-btn" :disabled="disabled || !text.trim()" type="button" title="发送" @click="handleSend">
          <Send :size="15" />
        </button>
      </div>
    </div>
    <AttachmentBlocks
      v-if="centered && attachments?.length"
      class="input-attachments centered-attachments"
      :attachments="attachments"
      align="left"
      @remove="emit('remove-attachment', $event)"
    />
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

.task-suggestions {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  align-items: center;
  justify-content: flex-start;
  pointer-events: auto;
}

.suggestion-button {
  max-width: 100%;
  min-height: 26px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.2;
}

.suggestion-button {
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast);
}

.suggestion-button:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-text);
  transform: translateY(-1px);
}

.suggestion-button:disabled {
  cursor: default;
  opacity: 0.5;
}

.input-attachments {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 1;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 0 var(--space-4);
  scrollbar-width: thin;
}

.input-attachments.centered-attachments {
  top: calc(100% + 8px);
  bottom: auto;
}

.input-container {
  container-type: inline-size;
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
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
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
  max-height: 140px;
  padding: 14px 14px 0;
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  color: var(--input-text);
  font-family: var(--font-ui);
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
  gap: var(--space-6);
  height: 38px;
  padding: 0 10px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 0 1 auto;
}

.attach-file-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast);
}

.attach-file-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-softer);
}

.file-input-hidden {
  display: none;
}

.web-search-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  border: 1px solid var(--color-primary);
  border-radius: 50%;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast);
}

.web-search-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.web-search-toggle.active {
  border-color: var(--color-primary);
  color: #fff;
  background: var(--color-primary);
}

.web-search-toggle:hover:not(:disabled) {
  border-color: var(--color-primary-hover);
  color: var(--color-primary-hover);
  background: var(--color-primary-softer);
}

.web-search-toggle.active:hover:not(:disabled) {
  border-color: var(--color-primary-hover);
  color: #fff;
  background: var(--color-primary-hover);
}

.access-mode-dropdown {
  position: relative;
  flex: 0 0 auto;
}

.access-mode-dropdown.disabled {
  pointer-events: none;
  opacity: 0.55;
}

.access-mode-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 26px;
  min-width: 64px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted, #8b93a7);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  line-height: 1;
  list-style: none;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.access-mode-trigger::-webkit-details-marker {
  display: none;
}

.access-mode-trigger::marker {
  content: '';
}

.access-mode-trigger:hover,
.access-mode-dropdown[open] .access-mode-trigger {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.access-mode-label {
  color: inherit;
  white-space: nowrap;
}

.access-mode-caret {
  color: inherit;
  transition: transform 120ms ease;
}

.access-mode-dropdown[open] .access-mode-caret {
  transform: rotate(180deg);
}

.access-mode-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: 180px;
  padding: 4px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 10px;
  background: var(--color-surface, #111827);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
  animation: loop-menu-pop 140ms ease-out both;
}

.access-mode-option {
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
  font-family: var(--font-ui);
  text-align: left;
  cursor: pointer;
  opacity: 0;
  transform: translateY(-4px);
  animation: loop-option-drop 150ms ease-out both;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.access-mode-option:nth-child(2) {
  animation-delay: 26ms;
}

.access-mode-option:nth-child(3) {
  animation-delay: 52ms;
}

.access-mode-option:hover,
.access-mode-option.active {
  background: var(--color-primary-softer);
  color: var(--color-text, #e5e7eb);
}

.access-mode-option-label {
  width: 54px;
  color: inherit;
  font-size: calc(11px * var(--font-scale));
}

.access-mode-option-hint {
  flex: 1;
  color: var(--color-text-muted, #7c8496);
  font-size: calc(10px * var(--font-scale));
}

.access-mode-check {
  color: var(--color-primary);
}

.model-config-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  min-width: 0;
  height: 28px;
  margin-left: auto;
  padding: 0 var(--space-10);
  border: 1px solid color-mix(in srgb, var(--color-primary) 46%, var(--color-border));
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  line-height: 1;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.model-config-trigger span {
  overflow: hidden;
  min-width: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-config-trigger:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-text-primary);
}

.model-config-trigger:disabled {
  cursor: default;
  opacity: 0.55;
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
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
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
  animation: loop-menu-pop 140ms ease-out both;
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
  font-family: var(--font-ui);
  text-align: left;
  cursor: pointer;
  opacity: 0;
  transform: translateY(-4px);
  animation: loop-option-drop 150ms ease-out both;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.loop-mode-menu .loop-mode-option:nth-of-type(1) { animation-delay: 20ms; }
.loop-mode-menu .loop-mode-option:nth-of-type(2) { animation-delay: 38ms; }
.loop-mode-menu .loop-mode-option:nth-of-type(3) { animation-delay: 56ms; }
.loop-mode-menu .loop-mode-option:nth-of-type(4) { animation-delay: 74ms; }

.loop-mode-option:hover,
.loop-mode-option.active {
  background: rgba(66, 36, 235, 0.14);
  color: var(--color-text, #e5e7eb);
}

.loop-mode-option-label {
  color: inherit;
  font-size: calc(12px * var(--font-scale));
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.02em;
}

.loop-mode-option-hint {
  margin-left: auto;
  color: var(--color-text-tertiary, #7c8496);
  font-size: calc(10px * var(--font-scale));
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
  flex: 0 0 30px;
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

@keyframes loop-menu-pop {
  from { transform: translateY(6px); }
  to { transform: translateY(0); }
}

@keyframes loop-option-drop {
  from { transform: translateY(-4px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent);
  color: #0a0a0a;
}

.send-btn:disabled {
  cursor: default;
  opacity: 0.35;
}

@container (max-width: 360px) {
  .model-config-trigger {
    flex: 0 0 30px;
    width: 30px;
    padding: 0;
  }

  .model-config-trigger span {
    display: none;
  }
}

@container (max-width: 320px) {
  .attach-file-btn {
    display: none;
  }
}

@container (max-width: 288px) {
  .web-search-toggle {
    display: none;
  }
}

@container (max-width: 252px) {
  .access-mode-trigger {
    min-width: 30px;
    padding: 0;
  }

  .access-mode-label,
  .access-mode-caret {
    display: none;
  }
}
</style>
