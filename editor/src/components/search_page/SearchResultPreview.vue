<!--
  Search result readonly file preview.

  Usage:
  SearchPage supplies a resolved knowledge file path and optional lexical
  query. Text is rendered through the shared CodeEditor in readonly mode;
  binary files fall back to the shared multimodal preview surface.
-->
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { previewKnowledgeFile, readKnowledgeFile } from '@/api/knowledge'
import CodeEditor from '@/components/editor_workspace/CodeEditor.vue'
import CodePreview from '@/components/editor_workspace/CodePreview.vue'
import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import { useSettingsStore } from '@/stores/settings'
import type { EditorViewMode, EditorWorkspaceMode, FilePreviewPayload } from '@/types/knowledge'

defineOptions({ name: 'SearchResultPreview' })

const props = defineProps<{
  path: string
  highlightQuery: string
}>()

const emit = defineEmits<{
  close: []
}>()

const settingsStore = useSettingsStore()
/** File text shown by the shared readonly editor surface. */
const content = ref('')
/** Multimodal payload used when a file has no extracted text. */
const preview = ref<FilePreviewPayload | null>(null)
/** Loading state for the currently selected result. */
const loading = ref(false)
/** User-facing load failure for the currently selected result. */
const error = ref('')
/** Local view mode; it never changes the readonly policy of this preview. */
const editorMode = ref<EditorViewMode>('edit')
let requestController: AbortController | null = null

/** File extensions that must use the backend preview endpoint. */
const previewExtensions = new Set([
  'avif', 'bmp', 'csv', 'docx', 'gif', 'ico', 'jpeg', 'jpg', 'pdf',
  'png', 'ppt', 'pptx', 'svg', 'tsv', 'webp', 'xlsx',
])

/** Compact filename shown in the preview header. */
const fileName = computed(() => {
  const parts = props.path.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? props.path
})

/** Language identifier reused by CodeEditor for the selected file. */
const language = computed(() => {
  const dotIndex = fileName.value.lastIndexOf('.')
  if (dotIndex < 0) return 'text'
  const extension = fileName.value.slice(dotIndex + 1).toLowerCase()
  return extension === 'txt' ? 'text' : extension
})

/** Whether the selected result supports Markdown rendering. */
const isMarkdown = computed(() => ['md', 'markdown'].includes(language.value))
/** Binary results without extracted text can only use Preview mode. */
const isPreviewOnly = computed(() => !content.value)
/** View mode normalized for files that cannot expose an editable text surface. */
const effectiveEditorMode = computed<EditorViewMode>(() => (
  isPreviewOnly.value ? 'preview' : editorMode.value
))

/** Loads text or multimodal data without changing the workspace selection. */
async function loadSelectedFile() {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  content.value = ''
  preview.value = null
  error.value = ''
  loading.value = true
  try {
    if (previewExtensions.has(language.value)) {
      const payload = await previewKnowledgeFile(settingsStore.profile.userId, props.path, controller.signal)
      if (controller.signal.aborted) return
      preview.value = payload
      content.value = payload.content ?? ''
      return
    }
    const response = await readKnowledgeFile(settingsStore.profile.userId, props.path, controller.signal)
    if (!controller.signal.aborted) {
      content.value = response.content
    }
  } catch (reason) {
    if (!controller.signal.aborted) {
      error.value = reason instanceof Error ? reason.message : '文件预览加载失败'
    }
  } finally {
    if (requestController === controller) {
      loading.value = false
    }
  }
}

watch(() => props.path, () => {
  editorMode.value = 'edit'
  void loadSelectedFile()
}, { immediate: true })

function setEditorMode(mode: EditorWorkspaceMode) {
  if (mode === 'edit' || mode === 'preview' || mode === 'split') editorMode.value = mode
}

onUnmounted(() => requestController?.abort())
</script>

<template>
  <aside class="search-result-preview" aria-label="搜索结果只读预览">
    <header class="preview-header">
      <div class="preview-title">
        <strong :title="fileName">{{ fileName }}</strong>
        <span :title="path">{{ path }}</span>
      </div>
      <span class="readonly-label">只读</span>
      <EditorModeSwitch
        :model-value="effectiveEditorMode"
        :preview-only="isPreviewOnly"
        @update:model-value="setEditorMode"
      />
      <button type="button" title="关闭预览" aria-label="关闭预览" @click="emit('close')">
        <IcIcon name="close" :size="16" />
      </button>
    </header>

    <div v-if="loading" class="preview-state">
      <IcIcon name="spinner" :size="18" class="preview-spinner" />
      <span>正在加载文件…</span>
    </div>
    <div v-else-if="error" class="preview-state preview-error">{{ error }}</div>
    <div
      v-else-if="content || preview"
      class="preview-body"
      :data-mode="effectiveEditorMode"
    >
      <section v-if="content && effectiveEditorMode !== 'preview'" class="preview-surface">
        <CodeEditor
          v-model="content"
          :language="language"
          :highlight-query="highlightQuery"
          readonly
        />
      </section>
      <div v-if="effectiveEditorMode === 'split'" class="preview-divider"></div>
      <section
        v-if="isPreviewOnly || effectiveEditorMode !== 'edit'"
        class="preview-surface"
      >
        <MultimodalPreview v-if="preview" :preview="preview" />
        <MarkdownPreview
          v-else-if="content && isMarkdown"
          :content="content"
          :path="path"
        />
        <CodePreview
          v-else-if="content"
          :content="content"
          :language="language"
        />
      </section>
    </div>
    <div v-else class="preview-state">没有可预览的内容</div>
  </aside>
</template>

<style scoped>
.search-result-preview {
  position: relative;
  align-self: stretch;
  display: flex;
  min-width: 0;
  height: 100%;
  min-height: calc(100vh - 180px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-canvas);
  box-shadow: none;
}

.preview-header {
  display: flex;
  min-height: 48px;
  align-items: center;
  gap: var(--space-8);
  padding: 0 var(--space-10);
  border: 0;
}

.preview-title {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.preview-title strong,
.preview-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-title strong {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.preview-title span,
.readonly-label {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.preview-header button {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.preview-header button:hover {
  background: var(--color-bg-hover);
  color: var(--color-text);
}

.preview-header button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.preview-state {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.preview-error {
  color: var(--color-danger);
}

.preview-spinner {
  animation: preview-spin 700ms linear infinite;
}

.preview-body {
  display: grid;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.preview-body[data-mode='edit'],
.preview-body[data-mode='preview'] {
  grid-template-columns: minmax(0, 1fr);
}

.preview-body[data-mode='split'] {
  grid-template-columns: minmax(0, 1fr) 6px minmax(0, 1fr);
}

.preview-surface {
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.preview-surface > * {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.preview-divider {
  background: var(--color-canvas-soft);
}

/* The search preview is intentionally one continuous surface without any
   nested strokes, including borders owned by reused editor components. */
.search-result-preview :deep(*) {
  border: 0 !important;
}

@keyframes preview-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .preview-spinner {
    animation: none;
  }
}

@media (max-width: 1120px) {
  .preview-title span,
  .readonly-label {
    display: none;
  }
}
</style>
