<!--
  Main editor pane.

  Usage:
  Renders open tabs, file metadata, Vditor edit surface, preview surface, and
  save/view-mode controls.
-->
<script setup lang="ts">
import { computed, nextTick, onErrorCaptured, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import IcIcon from '@/components/common/IcIcon.vue'
import CodeEditor from '@/components/editor_workspace/CodeEditor.vue'
import CodePreview from '@/components/editor_workspace/CodePreview.vue'
import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import MarkdownHtmlVisualizationPanel from '@/components/editor_workspace/MarkdownHtmlVisualizationPanel.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { EditorWorkspaceMode } from '@/types/knowledge'
import { resolveEditorFilePipeline } from '@/utils/editorFilePipeline'
import { fetchSessionChanges } from '@/api/agentChanges'
import { useSessionStore } from '@/stores/session'

const workspaceStore = useWorkspaceStore()
const sessionStore = useSessionStore()
const { editorMode } = storeToRefs(workspaceStore)
const visualizeMenuOpen = ref(false)
const codeEditorRef = ref<InstanceType<typeof CodeEditor> | null>(null)
const markdownPreviewRef = ref<InstanceType<typeof MarkdownPreview> | null>(null)
const lastEditorScroll = ref({ ratio: 0, cursorOffset: 0, contentLength: 0 })

const splitRatio = ref(0.5)
const splitBodyRef = ref<HTMLElement | null>(null)
let isDragging = false

function onSplitDividerPointerdown(event: PointerEvent) {
  if (event.button !== 0) return
  isDragging = true
  event.preventDefault()
  document.addEventListener('pointermove', onSplitDividerPointermove)
  document.addEventListener('pointerup', onSplitDividerPointerup)
}

function onSplitDividerPointermove(event: PointerEvent) {
  if (!isDragging || !splitBodyRef.value) return
  const rect = splitBodyRef.value.getBoundingClientRect()
  const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  splitRatio.value = x
}

function onSplitDividerPointerup() {
  isDragging = false
  document.removeEventListener('pointermove', onSplitDividerPointermove)
  document.removeEventListener('pointerup', onSplitDividerPointerup)
}

const activeContent = computed({
  get: () => workspaceStore.activeContent,
  set: (value: string) => workspaceStore.updateActiveContent(value),
})

const activeLanguage = computed(() => {
  const name = workspaceStore.selectedPath.toLowerCase()
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex < 0) {
    return 'text'
  }
  const extension = name.slice(dotIndex + 1)
  if (extension === 'txt') {
    return 'text'
  }
  return extension
})
const latestChangeSnapshot = ref<Awaited<ReturnType<typeof fetchSessionChanges>>['change_snapshot']>(null)
const activeChangeRanges = computed(() => {
  const snapshot = latestChangeSnapshot.value
  if (!snapshot) return []
  return snapshot.edits.flatMap((edit) => {
    if (edit.path !== workspaceStore.selectedPath || activeContent.value !== edit.after) return []
    const beforeLines = (edit.before ?? '').split('\n')
    const afterLines = edit.after.split('\n')
    let prefix = 0
    while (prefix < beforeLines.length && prefix < afterLines.length && beforeLines[prefix] === afterLines[prefix]) prefix += 1
    let suffix = 0
    while (
      suffix < beforeLines.length - prefix
      && suffix < afterLines.length - prefix
      && beforeLines[beforeLines.length - 1 - suffix] === afterLines[afterLines.length - 1 - suffix]
    ) suffix += 1
    const afterChanged = Math.max(0, afterLines.length - prefix - suffix)
    const beforeChanged = Math.max(0, beforeLines.length - prefix - suffix)
    const line = prefix + 1
    return [
      ...(afterChanged ? [{ startLine: line, endLine: line + afterChanged - 1, kind: 'added' as const }] : []),
      ...(beforeChanged ? [{ startLine: line, endLine: line, kind: 'removed' as const }] : []),
    ]
  })
})

async function loadLatestChangeSnapshot() {
  const sessionId = sessionStore.currentSessionId
  if (!sessionId) { latestChangeSnapshot.value = null; return }
  try {
    latestChangeSnapshot.value = (await fetchSessionChanges(sessionId)).change_snapshot
  } catch {
    latestChangeSnapshot.value = null
  }
}

const isMarkdownViewer = computed(() => workspaceStore.activeViewerKind === 'markdown')
const activePipeline = computed(() => resolveEditorFilePipeline(
  workspaceStore.selectedPath,
  workspaceStore.activePreview?.kind,
))
const effectiveEditorMode = computed<EditorWorkspaceMode>(() => (
  activePipeline.value.modes.some((item) => item.mode === editorMode.value)
    ? editorMode.value
    : activePipeline.value.defaultMode
))
const isEditableTextMode = computed(() => (
  ['edit', 'text', 'code'].includes(effectiveEditorMode.value)
  || (isMarkdownViewer.value && effectiveEditorMode.value === 'split')
))
const isProjectionMode = computed(() => effectiveEditorMode.value === 'markdown')

const splitBodyStyle = computed(() => {
  if (effectiveEditorMode.value !== 'split') return {}
  const r = Math.max(0.15, Math.min(0.85, splitRatio.value))
  return { gridTemplateColumns: `${r * 100}% 6px ${(1 - r) * 100}%` } as const
})

const visualizationOptions = [
  { key: 'strongMotion', label: '强动效' },
  { key: 'shadow', label: '阴影' },
  { key: 'rounded', label: '圆角' },
  { key: 'emoji', label: 'emoji' },
] as const

function handleVisualizationStart() {
  visualizeMenuOpen.value = false
  void workspaceStore.startMarkdownHtmlVisualization()
}

function handleVisualizationOptionChange(
  key: typeof visualizationOptions[number]['key'],
  event: Event,
) {
  workspaceStore.setMarkdownHtmlVisualizationOption(key, (event.target as HTMLInputElement).checked)
}

function setEditorMode(mode: EditorWorkspaceMode) {
  if (!activePipeline.value.modes.some((item) => item.mode === mode)) return
  editorMode.value = mode
}

function handleEditorScroll(payload: { ratio: number; cursorOffset: number; contentLength: number }) {
  lastEditorScroll.value = payload
  if (effectiveEditorMode.value === 'split' && isMarkdownViewer.value) {
    markdownPreviewRef.value?.scrollToRatio(payload.ratio)
  }
}

function handlePreviewScroll(ratio: number) {
  if (effectiveEditorMode.value === 'split' && isMarkdownViewer.value) {
    codeEditorRef.value?.scrollToRatio(ratio)
  }
}

function handleMarkdownPreviewReady() {
  if (effectiveEditorMode.value !== 'split' || !isMarkdownViewer.value) {
    return
  }
  const snapshot = codeEditorRef.value?.getScrollSnapshot() ?? lastEditorScroll.value
  markdownPreviewRef.value?.scrollToSourceOffset(snapshot.cursorOffset, snapshot.contentLength)
}

watch(effectiveEditorMode, async (mode, previousMode) => {
  if (mode !== 'split' || previousMode === 'split' || !isMarkdownViewer.value) {
    return
  }
  await nextTick()
  const snapshot = codeEditorRef.value?.getScrollSnapshot() ?? lastEditorScroll.value
  lastEditorScroll.value = snapshot
  markdownPreviewRef.value?.scrollToSourceOffset(snapshot.cursorOffset, snapshot.contentLength)
})

watch(() => workspaceStore.selectedPath, () => {
  void loadLatestChangeSnapshot()
})

watch(() => sessionStore.currentSessionId, () => void loadLatestChangeSnapshot(), { immediate: true })

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!workspaceStore.hasDirtyTabs) {
    return
  }
  event.preventDefault()
  event.returnValue = ''
}

function handleEditorShortcut(event: KeyboardEvent) {
  const isModifier = event.ctrlKey || event.metaKey
  if (!isModifier || event.altKey || event.shiftKey) {
    return
  }
  const target = event.target
  if (!(target instanceof HTMLElement) || !target.closest('.editor-panel')) {
    return
  }
  const key = event.key.toLowerCase()
  if (!isMarkdownViewer.value) return
  const modeByKey: Record<string, EditorWorkspaceMode> = {
    e: 'edit',
    p: 'preview',
    t: 'split',
  }
  const nextMode = modeByKey[key]
  if (!nextMode) {
    return
  }
  event.preventDefault()
  setEditorMode(nextMode)
}

/** Refreshes the persisted Agent patch after a streamed turn completes. */
function handleAgentTurnFinished() {
  void loadLatestChangeSnapshot()
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('agent-turn-finished', handleAgentTurnFinished)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('agent-turn-finished', handleAgentTurnFinished)
})

onErrorCaptured((err, vm, info) => {
  console.warn(`[EditorPane] Caught error (${info}):`, err)
  // Prevent child-component errors (e.g. Vditor destruction during rapid file
  // switching) from taking down the entire editor pane.
  return false
})

</script>

<template>
  <main class="editor-panel surface-panel" @keydown.capture="handleEditorShortcut">
    <div class="tab-strip">
      <div class="tab-list">
        <button
          v-if="workspaceStore.activeTab"
          :key="workspaceStore.activeTab.path"
          class="tab-item"
          type="button"
          @click="workspaceStore.activateTab(workspaceStore.activeTab.path)"
        >
          <span class="tab-title">{{ workspaceStore.activeTab.title }}</span>
          <i v-if="workspaceStore.activeTab.dirty" class="dirty-dot"></i>
          <IcIcon name="close" class="tab-close" :size="13" @click.stop="workspaceStore.closeTab(workspaceStore.activeTab.path)" />
        </button>
      </div>

      <div class="tab-actions">
        <EditorModeSwitch
          :model-value="effectiveEditorMode"
          :options="activePipeline.modes"
          @update:model-value="setEditorMode"
        />
        <div class="visualize-menu" :class="{ open: visualizeMenuOpen }">
          <button
            class="visualize-trigger"
            type="button"
            :disabled="!workspaceStore.activeTab || workspaceStore.selectedNode?.isDir"
            @click="visualizeMenuOpen = !visualizeMenuOpen"
          >
            <IcIcon name="auto-awesome" :size="15" />
          </button>
          <div v-if="visualizeMenuOpen" class="visualize-popover">
            <div class="visualize-mode">
              <button
                type="button"
                :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'structure' }"
                @click="workspaceStore.setMarkdownHtmlVisualizationMode('structure')"
              >
                原结构
              </button>
              <button
                type="button"
                :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'insight' }"
                @click="workspaceStore.setMarkdownHtmlVisualizationMode('insight')"
              >
                AI提炼
              </button>
            </div>
            <div class="visualize-options">
              <label v-for="option in visualizationOptions" :key="option.key">
                <input
                  type="checkbox"
                  :checked="workspaceStore.markdownHtmlVisualizationOptions[option.key]"
                  @change="handleVisualizationOptionChange(option.key, $event)"
                />
                <span>{{ option.label }}</span>
              </label>
            </div>
            <button class="visualize-submit" type="button" @click="handleVisualizationStart">
              一键可视化
            </button>
          </div>
        </div>
        <button
          class="save-button"
          type="button"
          :disabled="workspaceStore.activeFileReadonly"
          @click="workspaceStore.saveActiveFile"
        >
          <IcIcon name="save" :size="15" />
          <span>Save</span>
        </button>
      </div>
    </div>

    <div
      v-if="workspaceStore.openTabs.length > 0"
      ref="splitBodyRef"
      class="editor-body"
      :data-mode="effectiveEditorMode"
      :style="splitBodyStyle"
    >
      <section v-if="isEditableTextMode" class="editor-surface">
        <CodeEditor
          ref="codeEditorRef"
          v-model="activeContent"
          :language="activeLanguage"
          :paste-image="workspaceStore.savePastedEditorImage"
          :readonly="workspaceStore.activeFileReadonly"
          :change-ranges="activeChangeRanges"
          @save="workspaceStore.saveActiveFile"
          @scroll="handleEditorScroll"
        />
      </section>
      <div
        v-if="effectiveEditorMode === 'split'"
        class="split-divider"
        @pointerdown="onSplitDividerPointerdown"
      ></div>
      <section v-if="isMarkdownViewer && ['preview', 'split'].includes(effectiveEditorMode)" class="preview-surface">
        <MarkdownPreview
          ref="markdownPreviewRef"
          :key="workspaceStore.selectedPath"
          :content="activeContent"
          :path="workspaceStore.selectedPath"
          @scroll="handlePreviewScroll"
          @update-content="activeContent = $event"
          @ready="handleMarkdownPreviewReady"
        />
      </section>
      <section v-else-if="isProjectionMode" class="preview-surface projection-source-surface">
        <CodePreview
          :content="workspaceStore.activePreview?.semantic_markdown ?? ''"
          language="markdown"
        />
      </section>
      <section v-else-if="!isEditableTextMode" class="preview-surface">
        <MultimodalPreview :preview="workspaceStore.activePreview" />
      </section>
    </div>
    <div v-else class="editor-empty">
      <p>选择文件以开始编辑。</p>
    </div>
    <MarkdownHtmlVisualizationPanel />
  </main>
</template>

<style scoped>
.editor-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  background: var(--color-canvas-soft);
  font-family: var(--font-ui);
}

.tab-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 34px;
  padding: var(--space-8) var(--space-10) 0;
  background: var(--color-canvas-soft);
}

.tab-list {
  display: flex;
  flex: 1;
  min-width: 0;
  overflow-x: hidden;
  overflow-y: hidden;
}

.tab-item {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 8px 16px;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
  width: min(260px, 45vw);
  max-width: min(260px, 45vw);
  height: 28px;
  padding: 0 var(--space-10);
  border: 0;
  border-radius: 999px;
  background: var(--color-tab-active);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  text-align: left;
  flex: 0 1 min(260px, 45vw);
}

.tab-title {
  justify-self: start;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dirty-dot {
  grid-column: 2;
  justify-self: center;
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
}

.tab-close {
  grid-column: 3;
  justify-self: end;
  flex: 0 0 auto;
  color: var(--color-text-muted);
}

.tab-close:hover {
  color: var(--color-text);
}

.tab-actions {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-shrink: 0;
  padding-bottom: var(--space-6);
}

.save-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 22px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    border-color var(--transition-fast);
}

.visualize-menu {
  position: relative;
  flex: 0 0 auto;
}

.visualize-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.visualize-trigger:hover,
.visualize-menu.open .visualize-trigger {
  background: var(--color-accent);
  color: white;
}

.visualize-submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 22px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast);
}

.visualize-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.visualize-popover {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  display: grid;
  width: min(280px, 78vw);
  gap: var(--space-8);
  padding: var(--space-10);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}

.visualize-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.visualize-mode button {
  height: 24px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-canvas-soft);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast);
}

.visualize-mode button.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.visualize-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-6);
}

.visualize-options label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
}

.visualize-options input {
  flex: 0 0 auto;
}

.visualize-submit {
  width: 100%;
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.save-button {
  padding: 0 var(--space-8);
  border: 0;
  color: var(--color-text);
}

.save-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.save-button:disabled:hover {
  background: transparent;
  color: var(--color-text-muted);
}

.editor-body {
  display: grid;
  flex: 1;
  min-height: 0;
  gap: var(--space-10);
  margin: 0 var(--space-10) var(--space-10);
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0 8px 8px 8px;
  background: var(--color-canvas);
}

.split-divider {
  cursor: col-resize;
  border-radius: 3px;
  background: var(--color-border);
  transition: background 120ms ease;
  min-height: 100%;
}

.split-divider:hover {
  background: var(--color-primary);
}

.editor-body[data-mode='split'] {
  gap: 0;
}

.editor-body[data-mode='edit'],
.editor-body[data-mode='preview'],
.editor-body[data-mode='text'],
.editor-body[data-mode='forms'],
.editor-body[data-mode='markdown'],
.editor-body[data-mode='code'],
.editor-body[data-mode='binary'] {
  grid-template-columns: minmax(0, 1fr);
}

.editor-surface,
.preview-surface {
  /* These min sizes are required for Split. Without them Vditor can force one
     pane to occupy the full row and leave the preview pane invisible. */
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.editor-surface > *,
.preview-surface > * {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.editor-body :deep(.code-editor),
.editor-body :deep(.code-preview),
.editor-body :deep(.markdown-preview),
.editor-body :deep(.multimodal-preview) {
  border: 0;
  border-radius: 0;
}

.editor-empty {
  display: grid;
  flex: 1;
  place-items: center;
  min-height: 0;
  color: var(--color-text-muted);
  background: var(--color-canvas-soft);
}

.editor-empty p {
  margin: 0;
  font-size: calc(13px * var(--font-scale));
}

@media (max-width: 920px) {
  .tab-strip {
    align-items: flex-start;
    flex-direction: column;
  }

  .tab-actions {
    width: 100%;
    overflow: hidden;
  }

  .visualize-trigger span,
  .save-button span {
    display: none;
  }

  .editor-body[data-mode='split'] {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
