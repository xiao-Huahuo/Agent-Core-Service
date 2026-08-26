<!--
  Compact Markdown cell editor.

  Usage:
  SmartFormsView renders text and smart-text cells through this component. It
  shows the shared Markdown reading view, enters source editing on double-click,
  and uploads pasted images through the form-owned assets callback.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MarkdownContent from '@/components/editor_workspace/agent_chat/MarkdownContent.vue'
import { buildMarkdownDownloadUrl, rewriteMarkdownImageUrls } from '@/components/editor_workspace/markdownImageUrls'
import { insertMarkdownImage } from '@/components/smart_forms/smartLiteratureTable'
import { useSettingsStore } from '@/stores/settings'

defineOptions({ name: 'SmartMarkdownCell' })

const props = defineProps<{
  /** Markdown source stored in the smart cell. */
  value: string
  /** Virtual Markdown path used to resolve form-relative image URLs. */
  path: string
  /** Whether the cell may enter source editing mode. */
  editable: boolean
  /** Whether the collapsed reading view should show escaped plain text. */
  plainWhenCollapsed?: boolean
  /** Whether to keep complete Markdown rendered locally in both row states. */
  inlineMarkdownPreview?: boolean
  /** Uploads an image into the active form assets directory. */
  uploadImage: (file: File) => Promise<{ name: string; relativePath: string }>
}>()

const COLLAPSED_CHARACTER_LIMIT = 200
const CONTENT_ANIMATION_MS = 220
const settingsStore = useSettingsStore()

const emit = defineEmits<{
  update: [value: string]
  uploadError: [error: unknown]
  resize: [expanded: boolean, height: number]
  'edit-resize': [height: number]
}>()

const editing = ref(false)
const expanded = ref(false)
const collapsing = ref(false)
const draft = ref(props.value)
const textarea = ref<HTMLTextAreaElement | null>(null)
const cellRoot = ref<HTMLDivElement | null>(null)
const displayValue = computed(() => props.inlineMarkdownPreview || expanded.value || props.value.length <= COLLAPSED_CHARACTER_LIMIT
  ? props.value
  : `${props.value.slice(0, COLLAPSED_CHARACTER_LIMIT)}...`)
const resolvedInlinePreview = computed(() => rewriteMarkdownImageUrls(displayValue.value, {
  currentFilePath: props.path,
  userId: settingsStore.profile.userId,
}))
const usesInteractivePreview = computed(() => /!\[[^\]]*\]\([^)]*\)/.test(displayValue.value)
  || /(?:^|\n)\s*\|[^\n]+\|\s*\n\s*\|?\s*:?-{3,}/.test(displayValue.value))
const canExpand = computed(() => props.value.length > COLLAPSED_CHARACTER_LIMIT
  || Boolean(props.plainWhenCollapsed && props.value))
let collapseTimer: ReturnType<typeof setTimeout> | undefined

watch(() => props.value, (value) => {
  if (!editing.value) draft.value = value
  if (value.length <= COLLAPSED_CHARACTER_LIMIT) expanded.value = false
})

/** Starts the row resize before swapping content so both expansion and collapse receive a transition frame. */
async function toggleExpanded(): Promise<void> {
  if (collapsing.value) return
  if (expanded.value) {
    collapsing.value = true
    emit('resize', false, 282)
    collapseTimer = setTimeout(() => {
      expanded.value = false
      collapsing.value = false
      collapseTimer = undefined
    }, CONTENT_ANIMATION_MS)
    return
  }
  expanded.value = true
  await nextTick()
  const markdownBody = cellRoot.value?.querySelector<HTMLElement>('.markdown-body')
  emit('resize', true, Math.max(282, markdownBody?.scrollHeight || 282))
}

onBeforeUnmount(() => {
  if (collapseTimer) clearTimeout(collapseTimer)
})

/** Opens source editing and places the caret at the end. */
async function startEditing(): Promise<void> {
  if (!props.editable) return
  draft.value = props.value
  editing.value = true
  await nextTick()
  textarea.value?.focus()
  textarea.value?.setSelectionRange(draft.value.length, draft.value.length)
  emitEditResize()
}

/** Reports the live source height so ordinary-table rows can grow with content. */
async function emitEditResize(): Promise<void> {
  await nextTick()
  const source = textarea.value
  if (!source) return
  source.style.height = 'auto'
  const height = source.scrollHeight
  source.style.height = '100%'
  emit('edit-resize', height)
}

/** Updates the draft and recalculates the editing row height without inner scrolling. */
function handleSourceInput(): void {
  emit('update', draft.value)
  emitEditResize()
}

/** Commits source edits and returns to the shared Markdown reading view. */
function finishEditing(): void {
  if (!editing.value) return
  editing.value = false
  if (draft.value !== props.value) emit('update', draft.value)
}

/** Keeps the cell focusable for keyboard interaction. */
function handleCellClick(): void {
  if (!editing.value) cellRoot.value?.focus()
}

/** Uploads clipboard images and inserts form-relative Markdown at the caret. */
async function handlePaste(event: ClipboardEvent): Promise<void> {
  if (!props.editable) return
  const images = [...(event.clipboardData?.items ?? [])]
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file))
  if (!images.length) return
  event.preventDefault()
  if (!editing.value) await startEditing()
  let cursor = textarea.value?.selectionStart ?? draft.value.length
  try {
    for (const image of images) {
      const uploaded = await props.uploadImage(image)
      const inserted = insertMarkdownImage(draft.value, cursor, uploaded.name, uploaded.relativePath)
      draft.value = inserted.value
      cursor = inserted.cursor
      emit('update', draft.value)
    }
  } catch (error) {
    emit('uploadError', error)
    return
  }
  await nextTick()
  textarea.value?.setSelectionRange(cursor, cursor)
}

/** Downloads the exact rendered image URL exposed by the shared preview. */
function downloadImage(src: string, name: string): void {
  const anchor = document.createElement('a')
  anchor.href = buildMarkdownDownloadUrl(src)
  anchor.download = name
  anchor.click()
}
</script>

<template>
  <div
    ref="cellRoot"
    class="smart-markdown-cell"
    :class="{ expanded, collapsing, 'inline-markdown-preview': inlineMarkdownPreview }"
    tabindex="0"
    @dblclick.stop="startEditing"
    @click="handleCellClick"
    @paste="handlePaste"
  >
    <button
      v-if="canExpand && !editing"
      class="smart-markdown-toggle"
      type="button"
      :title="expanded ? '收缩内容' : '展开内容'"
      @click.stop="toggleExpanded"
    >
      <IcIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="13" />
    </button>
    <textarea
      v-show="editing"
      ref="textarea"
      v-model="draft"
      class="smart-markdown-source"
      rows="1"
      :readonly="!editable"
      @input="handleSourceInput"
      @blur="finishEditing"
      @keydown.esc.prevent="finishEditing"
    ></textarea>
    <div v-if="!editing" class="smart-markdown-reading">
      <div
        v-if="plainWhenCollapsed && !expanded"
        class="smart-plain-text"
      >{{ displayValue }}</div>
      <MarkdownContent v-else-if="inlineMarkdownPreview" :content="resolvedInlinePreview" />
      <MarkdownPreview
        v-else-if="usesInteractivePreview"
        :content="displayValue"
        :path="path"
        compact
        image-download
        @update-content="emit('update', $event)"
        @download-image="downloadImage"
      />
      <MarkdownContent v-else :content="displayValue" />
    </div>
  </div>
</template>

<style scoped>
.smart-markdown-cell {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  outline: 0;
  user-select: text;
}

.smart-markdown-cell.collapsing {
  overflow: hidden;
}

.smart-markdown-cell.collapsing .smart-markdown-reading {
  position: absolute;
  inset: 0;
}

.smart-markdown-reading {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.smart-markdown-cell.inline-markdown-preview .smart-markdown-reading {
  position: absolute;
  inset: 0;
}

.smart-markdown-cell.expanded:not(.collapsing) .smart-markdown-reading {
  animation: smart-markdown-expand 220ms ease-out both;
}

.smart-markdown-cell.collapsing .smart-markdown-reading {
  animation: smart-markdown-collapse 220ms ease-in both;
}

.smart-markdown-toggle {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--color-primary) 28%, var(--color-border));
  border-radius: 50%;
  background: color-mix(in srgb, var(--color-surface-raised) 86%, transparent);
  color: var(--color-primary);
  cursor: pointer;
}

.smart-markdown-toggle:hover {
  background: var(--color-primary-softer);
}

.smart-markdown-cell:focus-visible {
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.smart-markdown-cell :deep(.markdown-body) {
  box-sizing: border-box;
  height: 100%;
  overflow: auto;
  transition: max-height 220ms ease, opacity 180ms ease;
  padding: 9px 11px;
  font-size: calc(13px * var(--font-scale));
  line-height: 1.35;
}

.smart-markdown-cell :deep(.markdown-body > :first-child) { margin-top: 0; }
.smart-markdown-cell :deep(.markdown-body > :last-child) { margin-bottom: 0; }

.smart-plain-text {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  height: 100%;
  overflow: hidden;
  padding: 9px 34px 9px 11px;
  color: var(--color-text);
  font: inherit;
  line-height: 1.35;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.smart-markdown-source {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-height: 0;
  resize: none;
  border: 0;
  outline: 0;
  padding: 9px 11px;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  line-height: 1.35;
}

@keyframes smart-markdown-expand {
  from { opacity: 0.35; clip-path: inset(0 0 72% 0); transform: translateY(-4px); }
  to { opacity: 1; clip-path: inset(0); transform: translateY(0); }
}

@keyframes smart-markdown-collapse {
  from { opacity: 1; clip-path: inset(0); transform: translateY(0); }
  to { opacity: 0.25; clip-path: inset(0 0 72% 0); transform: translateY(-4px); }
}
</style>
