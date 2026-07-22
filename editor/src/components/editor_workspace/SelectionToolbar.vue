<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Clipboard, Scissors, ClipboardPaste, MessageSquareText } from 'lucide-vue-next'

const emit = defineEmits<{
  ask: [text: string]
}>()

const visible = ref(false)
const style = ref({ top: '0px', left: '0px' })
let selectedText = ''

const TOOLBAR_HEIGHT = 36
const TOOLBAR_GAP = 6

function getSelectionCoords(): { top: number; left: number; width: number } | null {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed || !selection.rangeCount) return null
  const range = selection.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  if (!rect || rect.width === 0) return null
  return { top: rect.top, left: rect.left, width: rect.width }
}

function getSelectedText(): string {
  return window.getSelection()?.toString().trim() || ''
}

function isSelectionInsideEditor(): boolean {
  const selection = window.getSelection()
  if (!selection || !selection.rangeCount) return false
  const node = selection.getRangeAt(0).commonAncestorContainer
  const el = node instanceof Element ? node : node.parentElement
  return el?.closest('.vditor-reset, .editor-panel') !== null
}

function updatePosition() {
  const coords = getSelectionCoords()
  if (!coords) {
    visible.value = false
    return
  }
  style.value = {
    top: `${coords.top - TOOLBAR_HEIGHT - TOOLBAR_GAP + window.scrollY}px`,
    left: `${coords.left + coords.width / 2 + window.scrollX}px`,
  }
}

function showToolbar() {
  const text = getSelectedText()
  if (!text || text.length < 2) {
    visible.value = false
    return
  }
  selectedText = text
  updatePosition()
  visible.value = true
}

function hideToolbar() {
  visible.value = false
  selectedText = ''
}

async function handleCopy() {
  if (!selectedText) return
  await navigator.clipboard.writeText(selectedText)
  hideToolbar()
}

async function handleCut() {
  if (!selectedText) return
  await navigator.clipboard.writeText(selectedText)
  document.execCommand('delete')
  hideToolbar()
}

async function handlePaste() {
  const text = await navigator.clipboard.readText()
  if (!text) return
  const vditorHost = document.querySelector('.vditor-reset') as HTMLElement
  if (vditorHost) {
    vditorHost.focus()
    document.execCommand('insertText', false, text)
  }
  hideToolbar()
}

function handleAsk() {
  if (!selectedText) return
  emit('ask', selectedText)
  hideToolbar()
}

function onSelectionChange() {
  if (isSelectionInsideEditor()) {
    showToolbar()
  } else {
    hideToolbar()
  }
}

onMounted(() => {
  document.addEventListener('selectionchange', onSelectionChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', onSelectionChange)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="selection-toolbar"
      :style="style"
      @mousedown.prevent
    >
      <button class="tb-btn" type="button" title="复制" @click="handleCopy">
        <Clipboard :size="13" />
        <span>复制</span>
      </button>
      <button class="tb-btn" type="button" title="剪切" @click="handleCut">
        <Scissors :size="13" />
        <span>剪切</span>
      </button>
      <button class="tb-btn" type="button" title="粘贴" @click="handlePaste">
        <ClipboardPaste :size="13" />
        <span>粘贴</span>
      </button>
      <div class="tb-divider"></div>
      <button class="tb-btn tb-btn-ask" type="button" title="提问" @click="handleAsk">
        <MessageSquareText :size="13" />
        <span>提问</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.selection-toolbar {
  position: absolute;
  z-index: 999;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 6px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  transform: translateX(-50%);
  white-space: nowrap;
  pointer-events: none;
}

.tb-btn {
  pointer-events: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
  cursor: pointer;
  transition: background 120ms, color 120ms;
}

.tb-btn:hover {
  background: var(--color-surface-active);
  color: var(--color-text);
}

.tb-btn-ask:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.tb-divider {
  width: 1px;
  height: 18px;
  margin: 0 4px;
  background: var(--color-border);
}
</style>
