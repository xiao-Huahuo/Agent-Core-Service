<!--
  Main editor pane.

  Usage:
  Renders open tabs, file metadata, Vditor edit surface, preview surface, and
  save/view-mode controls.
-->
<script setup lang="ts">
import { computed, nextTick, onErrorCaptured, onMounted, onUnmounted, ref, watch } from 'vue'
import { Columns2, Eye, Pencil, Save, Sparkles, X } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import CodeEditor from '@/components/editor_workspace/CodeEditor.vue'
import CodePreview from '@/components/editor_workspace/CodePreview.vue'
import MarkdownHtmlVisualizationPanel from '@/components/editor_workspace/MarkdownHtmlVisualizationPanel.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { EditorViewMode } from '@/types/knowledge'
import type { ComponentPublicInstance } from 'vue'

const workspaceStore = useWorkspaceStore()
const { editorMode } = storeToRefs(workspaceStore)
const segmentedRef = ref<HTMLElement | null>(null)
const modeButtonRefs = ref<HTMLElement[]>([])
const indicatorStyle = ref({ width: '0px', transform: 'translateX(0px)' })
const visualizeMenuOpen = ref(false)

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

const isMarkdownViewer = computed(() => workspaceStore.activeViewerKind === 'markdown')
const isCodeViewer = computed(() => ['code', 'text'].includes(workspaceStore.activeViewerKind))
const isPdfViewer = computed(() => workspaceStore.activeViewerKind === 'pdf')
const isPdfTextViewer = computed(() => isPdfViewer.value && Boolean(workspaceStore.activePreview?.content))
const isDocumentViewer = computed(() => workspaceStore.activeViewerKind === 'document')
const isDocumentTextViewer = computed(() => isDocumentViewer.value && Boolean(workspaceStore.activePreview?.content))
const isImageViewer = computed(() => workspaceStore.activeViewerKind === 'image')
const isImageTextViewer = computed(() => isImageViewer.value && Boolean(workspaceStore.activePreview?.content))
const isTextEditViewer = computed(() => isCodeViewer.value || isPdfTextViewer.value || isDocumentTextViewer.value || isImageTextViewer.value)
const isPreviewOnlyViewer = computed(() => !isMarkdownViewer.value && !isTextEditViewer.value)
const effectiveEditorMode = computed<EditorViewMode>(() => isPreviewOnlyViewer.value ? 'preview' : editorMode.value)

const splitBodyStyle = computed(() => {
  if (effectiveEditorMode.value !== 'split') return {}
  const r = Math.max(0.15, Math.min(0.85, splitRatio.value))
  return { gridTemplateColumns: `${r * 100}% 6px ${(1 - r) * 100}%` } as const
})

const modeButtons: Array<{ mode: EditorViewMode; label: string; icon: typeof Pencil }> = [
  { mode: 'edit', label: 'Edit', icon: Pencil },
  { mode: 'preview', label: 'Preview', icon: Eye },
  { mode: 'split', label: 'Split', icon: Columns2 },
]

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

let resizeObserver: ResizeObserver | null = null

function setModeButtonRef(element: Element | ComponentPublicInstance | null, index: number) {
  if (element instanceof HTMLElement) {
    modeButtonRefs.value[index] = element
  }
}

function moveSegmentedIndicatorToButton(activeButton: HTMLElement) {
  const segmented = segmentedRef.value
  if (!segmented) {
    return
  }
  const buttonRect = activeButton.getBoundingClientRect()
  const segmentedRect = segmented.getBoundingClientRect()
  indicatorStyle.value = {
    width: `${buttonRect.width}px`,
    transform: `translateX(${buttonRect.left - segmentedRect.left - 2}px)`,
  }
}

function updateSegmentedIndicator() {
  const activeIndex = modeButtons.findIndex((button) => button.mode === effectiveEditorMode.value)
  const activeButton = modeButtonRefs.value[activeIndex]
  if (!activeButton) {
    return
  }
  moveSegmentedIndicatorToButton(activeButton)
}

function setEditorMode(mode: EditorViewMode, event?: MouseEvent | PointerEvent) {
  if (isPreviewOnlyViewer.value && mode !== 'preview') {
    return
  }
  editorMode.value = mode
  if (event?.currentTarget instanceof HTMLElement) {
    moveSegmentedIndicatorToButton(event.currentTarget)
    return
  }
  void nextTick(updateSegmentedIndicator)
}

function handleModePointerdown(mode: EditorViewMode, event: PointerEvent) {
  if (event.button !== 0) {
    return
  }
  setEditorMode(mode, event)
}

function handleModeClick(mode: EditorViewMode, event: MouseEvent) {
  if (event.detail !== 0) {
    return
  }
  setEditorMode(mode, event)
}

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
  const modeByKey: Record<string, EditorViewMode> = {
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

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  resizeObserver = new ResizeObserver(updateSegmentedIndicator)
  if (segmentedRef.value) {
    resizeObserver.observe(segmentedRef.value)
  }
  void nextTick(updateSegmentedIndicator)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  resizeObserver?.disconnect()
  resizeObserver = null
})

onErrorCaptured((err, vm, info) => {
  console.warn(`[EditorPane] Caught error (${info}):`, err)
  // Prevent child-component errors (e.g. Vditor destruction during rapid file
  // switching) from taking down the entire editor pane.
  return false
})

watch(
  editorMode,
  () => {
    void nextTick(updateSegmentedIndicator)
  },
)

watch(
  isPreviewOnlyViewer,
  () => {
    void nextTick(updateSegmentedIndicator)
  },
)
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
          <X class="tab-close" :size="13" @click.stop="workspaceStore.closeTab(workspaceStore.activeTab.path)" />
        </button>
      </div>

      <div class="tab-actions">
        <div ref="segmentedRef" class="segmented">
          <span class="segmented-indicator" :style="indicatorStyle"></span>
          <button
            v-for="(button, index) in modeButtons"
            :key="button.mode"
            :ref="(element) => setModeButtonRef(element, index)"
            :class="{ active: effectiveEditorMode === button.mode }"
            :disabled="isPreviewOnlyViewer && button.mode !== 'preview'"
            type="button"
            @pointerdown="handleModePointerdown(button.mode, $event)"
            @click="handleModeClick(button.mode, $event)"
          >
            <component :is="button.icon" :size="14" />
            <span>{{ button.label }}</span>
          </button>
        </div>
        <div class="visualize-menu" :class="{ open: visualizeMenuOpen }">
          <button
            class="visualize-trigger"
            type="button"
            :disabled="!workspaceStore.activeTab || workspaceStore.selectedNode?.isDir"
            @click="visualizeMenuOpen = !visualizeMenuOpen"
          >
            <Sparkles :size="15" />
            <span>可视化</span>
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
          <Save :size="15" />
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
      <!-- Keep Edit and Preview as separate grid children. Split mode relies on
           this contract instead of Vditor's internal side-by-side preview. -->
      <section v-if="!isPreviewOnlyViewer && effectiveEditorMode !== 'preview'" class="editor-surface">
        <CodeEditor
          v-if="isMarkdownViewer || isTextEditViewer"
          v-model="activeContent"
          :language="isImageTextViewer ? 'ocr' : activeLanguage"
          :readonly="workspaceStore.activeFileReadonly"
          @save="workspaceStore.saveActiveFile"
        />
      </section>
      <div
        v-if="effectiveEditorMode === 'split'"
        class="split-divider"
        @pointerdown="onSplitDividerPointerdown"
      ></div>
      <section v-if="isPreviewOnlyViewer || effectiveEditorMode !== 'edit'" class="preview-surface">
        <MarkdownPreview
          v-if="isMarkdownViewer"
          :key="workspaceStore.selectedPath"
          :content="activeContent"
          :path="workspaceStore.selectedPath"
        />
        <CodePreview
          v-else-if="isCodeViewer && !isPdfViewer"
          :content="activeContent"
          :language="activeLanguage"
        />
        <MultimodalPreview v-else :preview="workspaceStore.activePreview" />
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
  transform: translateY(2px);
  padding: 0 var(--space-10);
  border: 0;
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
  background: var(--color-canvas);
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

.segmented {
  position: relative;
  display: inline-flex;
  padding: 2px;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canvas-soft);
}

.segmented-indicator {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 2px;
  z-index: 0;
  pointer-events: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  transition:
    transform 180ms ease,
    width 180ms ease;
}

.segmented button,
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

.segmented button {
  position: relative;
  z-index: 1;
}

.segmented button.active {
  color: white;
}

.segmented kbd {
  color: inherit;
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  opacity: 0.72;
}

.segmented button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.visualize-menu {
  position: relative;
  flex: 0 0 auto;
}

.visualize-trigger,
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

.visualize-trigger {
  padding: 0 var(--space-8);
}

.visualize-trigger:hover,
.visualize-menu.open .visualize-trigger {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
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
.editor-body[data-mode='preview'] {
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

  .segmented kbd {
    display: none;
  }

  .editor-body[data-mode='split'] {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
