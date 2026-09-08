<!--
  Scanner split result workspace.

  The left pane reuses the existing source editor/preview components; the right
  pane reuses CodeEditor, MarkdownPreview, and EditorModeSwitch for editable OCR
  and no-OCR drafts.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import CodeEditor from '@/components/editor_workspace/CodeEditor.vue'
import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import { fetchScanExport, saveScanToKnowledge, type ScannerRecord, type ScannerVariant } from '@/api/scanner'
import { previewKnowledgeFile } from '@/api/knowledge'
import { useScannerStore } from '@/stores/scanner'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { EditorWorkspaceMode, FilePreviewPayload } from '@/types/knowledge'

const props = defineProps<{ record: ScannerRecord }>()
const emit = defineEmits<{ back: []; updated: [record: ScannerRecord] }>()

const scannerStore = useScannerStore()
const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const variant = ref<ScannerVariant>(props.record.ocr_enabled ? 'ocr' : 'no_ocr')
const viewMode = ref<EditorWorkspaceMode>('split')
const markdownDraft = ref('')
const sourceDraft = ref('')
const sourcePreview = ref<FilePreviewPayload | null>(null)
const busyAction = ref('')
const actionMessage = ref('')
let draftTimer: number | null = null
let sourceTimer: number | null = null

const variantOptions = [
  { mode: 'edit' as EditorWorkspaceMode, label: 'OCR', icon: 'text-fields' },
  { mode: 'preview' as EditorWorkspaceMode, label: 'No OCR', icon: 'image' },
]
const viewOptions = [
  { mode: 'edit' as EditorWorkspaceMode, label: '编辑', icon: 'edit' },
  { mode: 'preview' as EditorWorkspaceMode, label: '预览', icon: 'visibility' },
  { mode: 'split' as EditorWorkspaceMode, label: '分栏', icon: 'view-column' },
]
const variantMode = computed<EditorWorkspaceMode>({
  get: () => variant.value === 'ocr' ? 'edit' : 'preview',
  set: (mode) => {
    const next = mode === 'edit' ? 'ocr' : 'no_ocr'
    if (next === variant.value) return
    flushDraftSave()
    variant.value = next
  },
})
const sourceEditable = computed(() => props.record.source_text !== null)
const sourceLanguage = computed(() => props.record.source_name.split('.').pop()?.toLowerCase() || 'text')
const virtualMarkdownPath = computed(() => `.mw/scan/${props.record.scan_id}/result.md`)

/** Replace local editor state when another history record or variant is selected. */
function syncDrafts(): void {
  markdownDraft.value = variant.value === 'ocr' ? props.record.ocr_markdown : props.record.no_ocr_markdown
  sourceDraft.value = props.record.source_text ?? ''
}

/** Load the original binary preview through the existing knowledge preview API. */
async function loadSourcePreview(): Promise<void> {
  sourcePreview.value = null
  if (sourceEditable.value || !props.record.source_path) return
  try {
    sourcePreview.value = await previewKnowledgeFile(settingsStore.profile.userId, props.record.source_path)
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '原文件预览失败'
  }
}

/** Debounce business-draft persistence through the scanner backend. */
function scheduleDraftSave(): void {
  if (draftTimer !== null) window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(async () => {
    draftTimer = null
    await scannerStore.saveDraft(variant.value, markdownDraft.value, props.record.scan_id)
    if (scannerStore.active) emit('updated', scannerStore.active)
  }, 500)
}

/** Debounce edits made to a text original stored in the managed scanner copy. */
function scheduleSourceSave(): void {
  if (sourceTimer !== null) window.clearTimeout(sourceTimer)
  sourceTimer = window.setTimeout(async () => {
    sourceTimer = null
    await scannerStore.saveSource(sourceDraft.value, props.record.scan_id)
    if (scannerStore.active) emit('updated', scannerStore.active)
  }, 500)
}

/** Flush a pending Markdown debounce before switching records or variants. */
function flushDraftSave(): void {
  if (draftTimer === null) return
  window.clearTimeout(draftTimer)
  draftTimer = null
  void scannerStore.saveDraft(variant.value, markdownDraft.value, props.record.scan_id)
}

/** Flush a pending original-text debounce before leaving the result page. */
function flushSourceSave(): void {
  if (sourceTimer === null) return
  window.clearTimeout(sourceTimer)
  sourceTimer = null
  void scannerStore.saveSource(sourceDraft.value, props.record.scan_id)
}

/** Resolve the absolute managed source path for native reveal. */
function absoluteSourcePath(): string {
  const root = settingsStore.profile.knowledgeDir.replace(/[\\/]+$/u, '')
  const child = props.record.source_path.replace(/\//gu, window.agentEditorDesktop?.platform === 'win32' ? '\\' : '/')
  return `${root}${window.agentEditorDesktop?.platform === 'win32' ? '\\' : '/'}${child}`
}

/** Reveal the managed original copy in the operating-system file manager. */
async function revealSource(): Promise<void> {
  await window.agentEditorDesktop?.showItemInFolder?.(absoluteSourcePath())
}

/** Toggle scanner favorites through the shared persisted favorites store. */
async function toggleFavorite(): Promise<void> {
  const favoritesStore = (await import('@/stores/favorites')).useFavoritesStore()
  await favoritesStore.toggle('scanner', props.record.scan_id, props.record.library_id)
  actionMessage.value = favoritesStore.isFavorite('scanner', props.record.scan_id, props.record.library_id) ? '已收藏' : '已取消收藏'
}

/** Save into the knowledge root after the existing conflict dialog resolves. */
async function saveToKnowledge(): Promise<void> {
  busyAction.value = 'save'
  actionMessage.value = ''
  try {
    await workspaceStore.loadKnowledgeTree()
    const filename = `${props.record.source_name.replace(/\.[^.]+$/u, '')}.md`
    const strategy = await workspaceStore.promptConflictStrategy('', [filename], 'scanner')
    if (!strategy) return
    const result = await saveScanToKnowledge(settingsStore.profile.userId, props.record.scan_id, variant.value, strategy)
    await workspaceStore.loadKnowledgeTree()
    actionMessage.value = `已保存到 ${result.path}`
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    busyAction.value = ''
  }
}

/** Fetch the backend package and open the native save-as dialog. */
async function exportOutside(): Promise<void> {
  busyAction.value = 'export'
  actionMessage.value = ''
  try {
    const result = await fetchScanExport(settingsStore.profile.userId, props.record.scan_id, variant.value)
    if (window.agentEditorDesktop?.saveFileAs) {
      const saved = await window.agentEditorDesktop.saveFileAs({ filename: result.filename, data: await result.blob.arrayBuffer() })
      actionMessage.value = saved ? `已导出到 ${saved}` : ''
      return
    }
    const url = URL.createObjectURL(result.blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = result.filename
    anchor.click()
    URL.revokeObjectURL(url)
    actionMessage.value = '已开始下载'
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '导出失败'
  } finally {
    busyAction.value = ''
  }
}

/** Copy one short or full scanner value to the system clipboard. */
async function copyText(value: string, label: string): Promise<void> {
  if (window.agentEditorDesktop?.writeClipboardText) await window.agentEditorDesktop.writeClipboardText(value)
  else await navigator.clipboard.writeText(value)
  actionMessage.value = `已复制${label}`
}

watch(() => [props.record.scan_id, variant.value, props.record.updated_at], syncDrafts, { immediate: true })
watch(() => props.record.scan_id, loadSourcePreview, { immediate: true })
watch(markdownDraft, scheduleDraftSave)
watch(sourceDraft, scheduleSourceSave)
onBeforeUnmount(() => {
  flushDraftSave()
  flushSourceSave()
})
</script>

<template>
  <section class="scanner-result">
    <header class="scanner-result-toolbar">
      <div class="scanner-result-title">
        <button type="button" title="返回上传页" aria-label="返回上传页" @click="emit('back')"><IcIcon name="back" :size="18" /></button>
        <strong :title="record.source_name">{{ record.source_name }}</strong>
        <button type="button" title="复制文件名" aria-label="复制文件名" @click="copyText(record.source_name, '文件名')"><IcIcon name="copy" :size="15" /></button>
      </div>
      <div class="scanner-result-actions">
        <button type="button" title="打开文件夹" aria-label="打开文件夹" @click="revealSource"><IcIcon name="folder-open" :size="17" /></button>
        <button type="button" title="收藏" aria-label="收藏" @click="toggleFavorite"><IcIcon name="star" :size="17" /></button>
        <button type="button" title="保存到知识库" aria-label="保存到知识库" :disabled="Boolean(busyAction)" @click="saveToKnowledge"><IcIcon name="save" :size="17" /></button>
        <button type="button" title="导出" aria-label="导出" :disabled="Boolean(busyAction)" @click="exportOutside"><IcIcon name="download" :size="17" /></button>
        <button type="button" title="复制全文" aria-label="复制全文" @click="copyText(markdownDraft, '全文')"><IcIcon name="copy" :size="17" /></button>
      </div>
    </header>
    <p v-if="actionMessage" class="scanner-action-message">{{ actionMessage }}</p>
    <div class="scanner-result-grid">
      <section class="scanner-source-pane">
        <header><strong>原文件</strong></header>
        <CodeEditor v-if="sourceEditable" v-model="sourceDraft" :language="sourceLanguage" @save="scannerStore.saveSource(sourceDraft, record.scan_id)" />
        <MultimodalPreview v-else :preview="sourcePreview" />
      </section>
      <section class="scanner-markdown-pane">
        <header>
          <EditorModeSwitch v-if="record.ocr_enabled" v-model="variantMode" class="variant-switch" :options="variantOptions" />
          <span v-else>Markdown</span>
          <EditorModeSwitch v-model="viewMode" class="view-switch" :options="viewOptions" />
        </header>
        <div class="scanner-markdown-body" :data-mode="viewMode">
          <CodeEditor v-if="viewMode === 'edit' || viewMode === 'split'" v-model="markdownDraft" language="markdown" @save="scannerStore.saveDraft(variant, markdownDraft, record.scan_id)" />
          <MarkdownPreview v-if="viewMode === 'preview' || viewMode === 'split'" :content="markdownDraft" :path="virtualMarkdownPath" />
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.scanner-result { position: relative; display: grid; grid-template-rows: auto minmax(0,1fr); width: 100%; height: 100%; min-width: 0; min-height: 0; background: var(--color-bg-app); }
.scanner-result-toolbar { display: flex; min-width: 0; min-height: 48px; align-items: center; justify-content: space-between; gap: 12px; padding: 7px 12px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.scanner-result-title,.scanner-result-actions { display: inline-flex; min-width: 0; align-items: center; gap: 4px; }
.scanner-result-title strong { max-width: min(42vw,520px); overflow: hidden; font-size: calc(13px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.scanner-result-toolbar button { display: grid; place-items: center; width: 30px; height: 30px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-secondary); transition: background 150ms ease, color 150ms ease, transform 120ms ease; }
.scanner-result-toolbar button:hover:not(:disabled) { background: var(--color-primary-softer); color: var(--color-primary); }
.scanner-result-toolbar button:active:not(:disabled) { transform: scale(.9); }
.scanner-result-toolbar button:disabled { opacity: .4; }
.scanner-action-message { position: absolute; top: 50px; right: 12px; z-index: 5; margin: 0; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 7px; background: var(--color-surface); color: var(--color-text-secondary); font-size: calc(11px * var(--font-scale)); box-shadow: 0 8px 22px rgba(0,0,0,.12); }
.scanner-result-grid { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); min-width: 0; min-height: 0; }
.scanner-source-pane,.scanner-markdown-pane { display: grid; grid-template-rows: 42px minmax(0,1fr); min-width: 0; min-height: 0; overflow: hidden; background: var(--color-canvas); }
.scanner-source-pane { border-right: 1px solid var(--color-border); }
.scanner-source-pane > header,.scanner-markdown-pane > header { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.scanner-source-pane > header strong,.scanner-markdown-pane > header > span { font-size: calc(12px * var(--font-scale)); }
.scanner-source-pane > :deep(.code-editor),.scanner-source-pane > :deep(.multimodal-preview) { min-width: 0; min-height: 0; border: 0; border-radius: 0; }
.scanner-markdown-body { display: grid; min-width: 0; min-height: 0; overflow: hidden; }
.scanner-markdown-body[data-mode='edit'],.scanner-markdown-body[data-mode='preview'] { grid-template-columns: minmax(0,1fr); }
.scanner-markdown-body[data-mode='split'] { grid-template-columns: minmax(0,1fr) minmax(0,1fr); }
.scanner-markdown-body > :deep(*) { min-width: 0; min-height: 0; border: 0; border-radius: 0; }
.scanner-markdown-body[data-mode='split'] > :deep(.code-editor) { border-right: 1px solid var(--color-border); }
@media (max-width: 1024px) { .scanner-markdown-body[data-mode='split'] { grid-template-columns: minmax(0,1fr); grid-template-rows: minmax(0,1fr) minmax(0,1fr); } .scanner-markdown-body[data-mode='split'] > :deep(.code-editor) { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 768px) { .scanner-result-grid { grid-template-columns: minmax(0,1fr); grid-template-rows: minmax(280px,42%) minmax(0,1fr); overflow: auto; } .scanner-source-pane { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 560px) { .scanner-markdown-pane > header { gap: 4px; } .view-switch :deep(button) { min-width: 32px; padding: 0 5px; } .view-switch :deep(button span) { display: none; } .variant-switch :deep(button) { min-width: 66px; padding: 0 5px; } }
@media (max-width: 480px) { .scanner-result-toolbar { align-items: flex-start; flex-direction: column; } .scanner-result-actions { width: 100%; justify-content: flex-end; } .scanner-result-title strong { max-width: calc(100vw - 150px); } }
@media (prefers-reduced-motion: reduce) { .scanner-result-toolbar button { transition: none; } }
</style>
