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
import BacklinksPanel from '@/components/editor_workspace/BacklinksPanel.vue'
import CodeEditor from '@/components/editor_workspace/CodeEditor.vue'
import CodePreview from '@/components/editor_workspace/CodePreview.vue'
import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import MarkdownHtmlVisualizationPanel from '@/components/editor_workspace/MarkdownHtmlVisualizationPanel.vue'
import MarkdownOutline from '@/components/editor_workspace/MarkdownOutline.vue'
import MarkdownPreview from '@/components/editor_workspace/MarkdownPreview.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useSettingsStore } from '@/stores/settings'
import type { EditorWorkspaceMode } from '@/types/knowledge'
import { resolveEditorFilePipeline } from '@/utils/editorFilePipeline'
import { fetchSessionChanges } from '@/api/agentChanges'
import { readKnowledgeFile } from '@/api/knowledge'
import { useSessionStore } from '@/stores/session'
import { buildBacklinks } from './backlinks'
import {
  flattenMarkdownOutline,
  headingAtOffset,
  parseMarkdownOutline,
  type MarkdownOutlineItem,
} from './markdownOutline'
import { flattenWikiFiles, parseWikiLink, resolveWikiTargetPath } from './wikiLinks'

const props = withDefaults(defineProps<{
  /** Whether this pane is embedded as the independent editor sidebar. */
  sidebar?: boolean
}>(), {
  sidebar: false,
})

const emit = defineEmits<{
  /** Requests that the parent hide the independent editor sidebar. */
  close: []
}>()

const workspaceStore = useWorkspaceStore()
const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const { editorMode } = storeToRefs(workspaceStore)
const visualizeMenuOpen = ref(false)
const codeEditorRef = ref<InstanceType<typeof CodeEditor> | null>(null)
const markdownPreviewRef = ref<InstanceType<typeof MarkdownPreview> | null>(null)
const lastEditorScroll = ref({ ratio: 0, cursorOffset: 0, contentLength: 0 })
const outlineOpen = ref(false)
const activeHeadingOffset = ref(0)
const wikiFocusAnchor = ref<{ path: string; heading: string; blockId: string; nonce: number } | null>(null)
let wikiFocusNonce = 0
const backlinkDocuments = ref<Record<string, string>>({})
const backlinksLoading = ref(false)
let backlinksLoadNonce = 0
const backlinks = computed(() => buildBacklinks(
  workspaceStore.selectedPath,
  workspaceStore.tree,
  backlinkDocuments.value,
))
const shouldShowBacklinks = computed(() => (
  Boolean(settingsStore.profile.showBacklinks)
  && isMarkdownViewer.value
  && Boolean(workspaceStore.activeTab)
))

async function loadBacklinks() {
  if (!shouldShowBacklinks.value || !settingsStore.profile.userId) {
    backlinkDocuments.value = {}
    return
  }
  const nonce = ++backlinksLoadNonce
  backlinksLoading.value = true
  try {
    if (workspaceStore.tree.length === 0) await workspaceStore.loadKnowledgeTree()
    const markdownFiles = flattenWikiFiles(workspaceStore.tree)
      .filter((node) => /\.(?:md|markdown)$/iu.test(node.path))
    const results = await Promise.allSettled(markdownFiles.map(async (node) => [
      node.path,
      node.path === workspaceStore.selectedPath
        ? activeContent.value
        : (await readKnowledgeFile(settingsStore.profile.userId, node.path)).content,
    ] as const))
    if (nonce !== backlinksLoadNonce) return
    backlinkDocuments.value = Object.fromEntries(
      results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : []),
    )
  } finally {
    if (nonce === backlinksLoadNonce) backlinksLoading.value = false
  }
}

async function toggleBacklinks() {
  try {
    await settingsStore.setShowBacklinks(!settingsStore.profile.showBacklinks)
  } catch {
    workspaceStore.showToast('反向链接显示设置保存失败')
  }
}

async function closeBacklinks() {
  try {
    await settingsStore.setShowBacklinks(false)
  } catch {
    workspaceStore.showToast('反向链接显示设置保存失败')
  }
}

async function openBacklinkSource(path: string) {
  const node = workspaceStore.flatNodes.find((item) => !item.isDir && item.path === path)
  if (node) await workspaceStore.selectFile(node)
}

async function saveActiveFileAndRefreshBacklinks() {
  await workspaceStore.saveActiveFile()
  await loadBacklinks()
}

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
const outlineItems = computed(() => parseMarkdownOutline(activeContent.value))
const flatOutlineItems = computed(() => flattenMarkdownOutline(outlineItems.value))
const activeOutlineId = computed(() => (
  headingAtOffset(outlineItems.value, activeHeadingOffset.value)?.id ?? ''
))
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
  activeHeadingOffset.value = payload.cursorOffset
  if (effectiveEditorMode.value === 'split' && isMarkdownViewer.value) {
    markdownPreviewRef.value?.scrollToRatio(payload.ratio)
  }
}

/** Tracks the heading that owns the editable Markdown caret. */
function handleEditorCursor(offset: number) {
  activeHeadingOffset.value = offset
}

/** Maps the rendered preview heading order back to its Markdown source offset. */
function handlePreviewActiveHeading(index: number) {
  const heading = flatOutlineItems.value[index]
  if (heading) activeHeadingOffset.value = heading.offset
}

/** Navigates every visible Markdown surface to the selected outline heading. */
function navigateToOutlineHeading(item: MarkdownOutlineItem) {
  activeHeadingOffset.value = item.offset
  const index = flatOutlineItems.value.findIndex((heading) => heading.id === item.id)
  if (['edit', 'split'].includes(effectiveEditorMode.value)) {
    codeEditorRef.value?.scrollToSourceOffset(item.offset, 'smooth')
  }
  if (index >= 0 && ['preview', 'split'].includes(effectiveEditorMode.value)) {
    markdownPreviewRef.value?.scrollToHeading(index)
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

async function handleWikiNavigate(rawDestination: string) {
  const destination = parseWikiLink(rawDestination)
  if (!destination) return
  const targetPath = resolveWikiTargetPath(
    destination.file,
    workspaceStore.tree,
    workspaceStore.selectedPath,
  )
  const targetNode = workspaceStore.flatNodes.find((node) => !node.isDir && node.path === targetPath)
  if (!targetNode) {
    workspaceStore.showToast(`找不到链接文件：${destination.file}`)
    return
  }
  workspaceStore.setMainView('editor')
  await workspaceStore.selectFile(targetNode)
  if (/\.(?:md|markdown)$/iu.test(targetPath)) {
    workspaceStore.setEditorMode('preview')
    wikiFocusAnchor.value = {
      path: targetPath,
      heading: destination.heading,
      blockId: destination.blockId,
      nonce: ++wikiFocusNonce,
    }
  }
}

watch(effectiveEditorMode, async (mode, previousMode) => {
  if (!isMarkdownViewer.value || mode === previousMode) return
  await nextTick()

  const activeIndex = flatOutlineItems.value.findIndex((heading) => heading.id === activeOutlineId.value)
  if (previousMode === 'preview' && ['edit', 'split'].includes(mode)) {
    codeEditorRef.value?.scrollToSourceOffset(activeHeadingOffset.value, 'auto')
  }
  if (mode === 'preview') {
    if (activeIndex >= 0) markdownPreviewRef.value?.scrollToHeading(activeIndex)
    return
  }
  if (mode !== 'split' || previousMode === 'split') return

  const snapshot = codeEditorRef.value?.getScrollSnapshot() ?? lastEditorScroll.value
  lastEditorScroll.value = snapshot
  if (previousMode === 'preview' && activeIndex >= 0) {
    markdownPreviewRef.value?.scrollToHeading(activeIndex)
  } else {
    markdownPreviewRef.value?.scrollToSourceOffset(snapshot.cursorOffset, snapshot.contentLength)
  }
})

watch(() => workspaceStore.selectedPath, () => {
  activeHeadingOffset.value = 0
  void loadLatestChangeSnapshot()
  void loadBacklinks()
})

watch(isMarkdownViewer, (isMarkdown) => {
  if (!isMarkdown) outlineOpen.value = false
})

watch(() => settingsStore.profile.showBacklinks, () => void loadBacklinks())

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
  <main class="editor-panel surface-panel" :class="{ 'sidebar-editor-panel': props.sidebar }" @keydown.capture="handleEditorShortcut">
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
          class="editor-mode-control"
          :class="{ 'single-mode': activePipeline.modes.length === 1 }"
          :model-value="effectiveEditorMode"
          :options="activePipeline.modes"
          @update:model-value="setEditorMode"
        />
        <button
          v-if="isMarkdownViewer"
          class="editor-tool-button outline-toggle"
          :class="{ active: outlineOpen }"
          type="button"
          :aria-pressed="outlineOpen"
          title="目录树"
          @click="outlineOpen = !outlineOpen"
        >
          <IcIcon name="view-list" :size="15" />
          <span>目录树</span>
        </button>
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
          class="editor-tool-button save-button"
          type="button"
          :disabled="workspaceStore.activeFileReadonly"
          @click="workspaceStore.saveActiveFile"
        >
          <svg
            class="save-motion-icon"
            aria-hidden="true"
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path data-save-path="box" d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
            <path data-save-path="top" d="M7 3v5h8" />
            <path data-save-path="bottom" d="M17 20v-7H7v7" />
          </svg>
          <span>Save</span>
        </button>
        <button v-if="props.sidebar" class="sidebar-close-button" type="button" title="关闭编辑区侧边栏" aria-label="关闭编辑区侧边栏" @click="emit('close')">
          <IcIcon name="close" :size="15" />
        </button>
      </div>
    </div>

    <div
      v-if="workspaceStore.openTabs.length > 0"
      ref="splitBodyRef"
      class="editor-body"
      :class="{ 'with-backlinks': shouldShowBacklinks }"
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
          :wiki-files="workspaceStore.tree"
          :show-backlinks="Boolean(settingsStore.profile.showBacklinks)"
          @save="saveActiveFileAndRefreshBacklinks"
          @scroll="handleEditorScroll"
          @cursor="handleEditorCursor"
          @toggle-backlinks="toggleBacklinks"
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
          :focus-anchor="wikiFocusAnchor"
          @scroll="handlePreviewScroll"
          @active-heading="handlePreviewActiveHeading"
          @update-content="activeContent = $event"
          @ready="handleMarkdownPreviewReady"
          @navigate-wiki="handleWikiNavigate"
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
      <MarkdownOutline
        v-if="isMarkdownViewer"
        :items="outlineItems"
        :active-id="activeOutlineId"
        :open="outlineOpen"
        @navigate="navigateToOutlineHeading"
      />
    </div>
    <div v-else class="editor-empty">
      <p>选择文件以开始编辑。</p>
    </div>
    <BacklinksPanel
      v-if="shouldShowBacklinks"
      :entries="backlinks"
      :loading="backlinksLoading"
      @close="closeBacklinks"
      @open="openBacklinkSource"
    />
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

.sidebar-editor-panel {
  width: 100%;
  min-width: 0;
}

.sidebar-close-button {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.sidebar-close-button:hover {
  color: var(--color-text);
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

.editor-tool-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 22px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-family: inherit;
  font-size: calc(11px * var(--font-scale));
  cursor: pointer;
  transition:
    background 160ms ease,
    color 160ms ease,
    transform 140ms cubic-bezier(0.23, 1, 0.32, 1);
}

.editor-tool-button:active:not(:disabled) {
  transform: scale(0.94);
}

.outline-toggle.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.save-motion-icon,
.save-motion-icon path {
  overflow: visible;
  transform-origin: center;
  transition: transform 220ms cubic-bezier(0.23, 1, 0.32, 1);
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
  --save-tilt: -9deg;
}

.save-button:active:not(:disabled) .save-motion-icon {
  transform: rotate(-12deg) scale(0.82);
}

.save-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.save-button:disabled:hover {
  background: transparent;
  color: var(--color-text-muted);
}

@media (hover: hover) and (pointer: fine) {
  .editor-tool-button:hover:not(:disabled) {
    background: var(--color-primary-softer);
    color: var(--color-primary-hover);
  }

  .save-button:hover:not(:disabled) .save-motion-icon {
    transform: rotate(var(--save-tilt)) scale(1.1);
  }

  .save-button:hover:not(:disabled) [data-save-path='box'] {
    transform: translateY(1px) scale(1.04);
  }

  .save-button:hover:not(:disabled) [data-save-path='top'] {
    transform: translate(1.5px, 1.5px) scaleX(0.9);
  }

  .save-button:hover:not(:disabled) [data-save-path='bottom'] {
    transform: translateY(-2px) scaleY(0.9);
  }
}

.editor-body {
  position: relative;
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

.editor-body.with-backlinks {
  margin-bottom: var(--space-6);
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
  .save-button span,
  .outline-toggle span {
    display: none;
  }

  .editor-body[data-mode='split'] {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .editor-tool-button,
  .save-motion-icon,
  .save-motion-icon path {
    transition: color 160ms ease, background 160ms ease;
  }

  .editor-tool-button:active:not(:disabled),
  .save-button:hover:not(:disabled) .save-motion-icon,
  .save-button:hover:not(:disabled) [data-save-path] {
    transform: none;
  }
}
</style>
