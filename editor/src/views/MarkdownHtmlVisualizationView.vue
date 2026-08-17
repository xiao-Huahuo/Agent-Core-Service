<!--
  Markdown HTML visualization workspace page.

  Usage:
  Provides a visible page for configuring the Agent document visualization
  workflow and for mounting the generated runtime HTML.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import FloatingFileResourcePicker from '@/components/editor_workspace/FloatingFileResourcePicker.vue'
import { useSettingsStore } from '@/stores/settings'
import { useTaskListStore } from '@/stores/taskList'
import { useWorkspaceStore } from '@/stores/workspace'
import type { MarkdownHtmlVisualizationOptions, MarkdownHtmlVisualizationPreset } from '@/types/knowledge'

const settingsStore = useSettingsStore()
const taskListStore = useTaskListStore()
const workspaceStore = useWorkspaceStore()
const modeSwitchRef = ref<HTMLElement | null>(null)
const modeSliderStyle = ref({ width: '0px', left: '0px' })
const pickerOpen = ref(false)
const advancedOptionsOpen = ref(false)
const advancedOptionsPage = ref<'layout' | 'visual' | 'motion'>('layout')
const taskProgressCardVisible = ref(false)
const taskProgressExpanded = ref(false)

const visualizationPresets: Array<{ value: MarkdownHtmlVisualizationPreset; label: string }> = [
  { value: 'balanced', label: '均衡展示' },
  { value: 'reader', label: '阅读导向' },
  { value: 'dashboard', label: '仪表盘导向' },
  { value: 'magazine', label: '杂志导向' },
]

const advancedOptionPages: Array<{ value: typeof advancedOptionsPage.value; label: string }> = [
  { value: 'layout', label: '结构' },
  { value: 'visual', label: '视觉' },
  { value: 'motion', label: '动效' },
]

const visualizationOptionGroups: Record<typeof advancedOptionsPage.value, Array<{ key: keyof MarkdownHtmlVisualizationOptions; label: string }>> = {
  layout: [
    { key: 'visualHierarchy', label: '视觉层级' },
    { key: 'gridLayout', label: '网格系统' },
    { key: 'callouts', label: '重点标注' },
    { key: 'denseLayout', label: '高信息密度' },
  ],
  visual: [
    { key: 'typographyScale', label: '字体层级' },
    { key: 'contrast', label: '对比度' },
    { key: 'accentColor', label: '强调色' },
    { key: 'shadow', label: '阴影' },
    { key: 'rounded', label: '圆角' },
  ],
  motion: [
    { key: 'microInteractions', label: '微交互' },
    { key: 'scrollReveal', label: '滚动揭示' },
    { key: 'strongMotion', label: '强动效' },
    { key: 'emoji', label: 'emoji' },
  ],
}

const currentVisualizationOptions = computed(() => {
  return visualizationOptionGroups[advancedOptionsPage.value]
})

const taskStatusLabels: Record<string, string> = {
  pending: '等待',
  in_progress: '进行中',
  completed: '完成',
  failed: '失败',
}

const selectedDocumentLabel = computed(() => {
  const node = workspaceStore.selectedNode
  if (!node || node.isDir) {
    return '未选择文档'
  }
  return node.path
})

const knowledgeSaveDirectory = computed(() => {
  const userId = workspaceStore.markdownHtmlVisualization
    ? settingsStore.profile.userId
    : ''
  return userId ? `${userId}_html/` : '{user_id}_html/'
})

const hasMountedVisualization = computed(() => {
  return Boolean(workspaceStore.markdownHtmlVisualizationOpen && workspaceStore.markdownHtmlVisualization)
})

const visualizationActionLabel = computed(() => {
  return hasMountedVisualization.value ? '重新可视化' : '一键可视化'
})

const showTaskProgressCard = computed(() => {
  return taskProgressCardVisible.value
    && !hasMountedVisualization.value
    && taskListStore.taskList !== null
    && taskListStore.taskList.status !== 'completed'
})

const taskProgressText = computed(() => {
  const total = taskListStore.taskList?.items.length ?? 0
  return `${taskListStore.completedCount}/${total}`
})

const taskProgressPercent = computed(() => {
  const total = taskListStore.taskList?.items.length ?? 0
  if (total <= 0) return 0
  return Math.round((taskListStore.completedCount / total) * 100)
})

const taskProgressTitle = computed(() => {
  return taskListStore.taskList?.title || 'Agent 任务列表'
})

const taskProgressCurrent = computed(() => {
  return taskListStore.currentItem?.title || '等待 Agent 更新任务进度'
})

watch(() => taskListStore.eventSerial, () => {
  if (taskListStore.lastEventType === 'created' || taskListStore.lastEventType === 'updated') {
    if (taskListStore.lastEventType === 'created') {
      taskProgressExpanded.value = false
    }
    taskProgressCardVisible.value = true
    return
  }
  taskProgressCardVisible.value = false
})

watch(hasMountedVisualization, (mounted) => {
  if (mounted) {
    taskProgressCardVisible.value = false
  }
})

function updateModeSlider() {
  nextTick(() => {
    const container = modeSwitchRef.value
    if (!container) return
    const active = container.querySelector('.mode-button.active') as HTMLElement | null
    if (!active) return
    modeSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

function setMode(mode: 'structure' | 'insight') {
  workspaceStore.setMarkdownHtmlVisualizationMode(mode)
  updateModeSlider()
}

onMounted(updateModeSlider)

function setPreset(preset: MarkdownHtmlVisualizationPreset) {
  workspaceStore.setMarkdownHtmlVisualizationPreset(preset)
}

function setOption(key: keyof MarkdownHtmlVisualizationOptions, event: Event) {
  workspaceStore.setMarkdownHtmlVisualizationOption(key, (event.target as HTMLInputElement).checked)
}

function setCustomRequirement(event: Event) {
  workspaceStore.setMarkdownHtmlVisualizationCustomRequirement((event.target as HTMLTextAreaElement).value)
}

function startVisualization() {
  void workspaceStore.startMarkdownHtmlVisualization()
}
</script>

<template>
  <section class="visualization-page">
    <header class="visualization-toolbar">
      <div ref="modeSwitchRef" class="mode-pill">
        <div class="mode-slider" :style="modeSliderStyle"></div>
        <button
          type="button"
          class="mode-button"
          :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'structure' }"
          @click="setMode('structure')"
        >
          <IcIcon name="view-column" :size="17" />
          <span>原结构模式</span>
        </button>
        <button
          type="button"
          class="mode-button"
          :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'insight' }"
          @click="setMode('insight')"
        >
          <IcIcon name="auto-awesome" :size="17" />
          <span>AI提炼模式</span>
        </button>
      </div>
      <div class="toolbar-actions">
        <span class="selected-file-path" :title="selectedDocumentLabel">{{ selectedDocumentLabel }}</span>
        <button type="button" class="tool-button" title="选择文件" aria-label="选择文件" @click="pickerOpen = true">
          <IcIcon name="folder-open" :size="15" />
        </button>
        <div class="advanced-menu-wrap">
          <button
            type="button"
            class="secondary-action"
            :class="{ active: advancedOptionsOpen }"
            :aria-expanded="advancedOptionsOpen"
            aria-haspopup="menu"
            @click="advancedOptionsOpen = !advancedOptionsOpen"
          >
            <IcIcon name="tune" :size="15" />
            <span>高级选项</span>
            <IcIcon name="chevron-down" :size="14" />
          </button>
          <div v-if="advancedOptionsOpen" class="advanced-menu" role="menu">
            <section class="advanced-section">
              <span class="advanced-section-title">展示预设</span>
              <div class="preset-grid" aria-label="HTML 可视化展示预设">
                <button
                  v-for="preset in visualizationPresets"
                  :key="preset.value"
                  type="button"
                  :class="{ active: workspaceStore.markdownHtmlVisualizationPreset === preset.value }"
                  @click.stop="setPreset(preset.value)"
                >
                  {{ preset.label }}
                </button>
              </div>
            </section>
            <section class="advanced-section">
              <div class="advanced-page-tabs" aria-label="高级选项分页">
                <button
                  v-for="page in advancedOptionPages"
                  :key="page.value"
                  type="button"
                  :class="{ active: advancedOptionsPage === page.value }"
                  @click.stop="advancedOptionsPage = page.value"
                >
                  {{ page.label }}
                </button>
              </div>
              <div class="option-row">
                <label v-for="option in currentVisualizationOptions" :key="option.key">
                  <input
                    type="checkbox"
                    :checked="workspaceStore.markdownHtmlVisualizationOptions[option.key]"
                    @change="setOption(option.key, $event)"
                    @click.stop
                  />
                  <span>{{ option.label }}</span>
                </label>
              </div>
            </section>
            <label class="custom-requirement-field">
              <span>自定义要求</span>
              <textarea
                rows="3"
                placeholder="例如: 更像论文导读, 减少装饰, 突出关键结论"
                :value="workspaceStore.markdownHtmlVisualizationCustomRequirement"
                @input="setCustomRequirement"
                @click.stop
              ></textarea>
            </label>
          </div>
        </div>
        <button
          type="button"
          :disabled="!workspaceStore.selectedNode || workspaceStore.selectedNode.isDir || workspaceStore.refreshing"
          @click="startVisualization"
        >
          <IcIcon name="play" :size="15" />
          <span>{{ visualizationActionLabel }}</span>
        </button>
      </div>
    </header>

    <Transition name="task-progress-float">
      <aside v-if="showTaskProgressCard" class="task-progress-card" aria-live="polite">
        <div class="task-progress-head">
          <div>
            <span>{{ taskProgressTitle }}</span>
            <strong>{{ taskProgressText }}</strong>
          </div>
          <button
            type="button"
            class="task-progress-toggle"
            :aria-expanded="taskProgressExpanded"
            @click="taskProgressExpanded = !taskProgressExpanded"
          >
            <IcIcon name="chevron-down" :size="14" />
          </button>
        </div>
        <div class="task-progress-bar" aria-hidden="true">
          <span :style="{ width: `${taskProgressPercent}%` }"></span>
        </div>
        <p>{{ taskProgressCurrent }}</p>
        <Transition name="task-list-expand">
          <ol v-if="taskProgressExpanded" class="task-progress-list">
            <li
              v-for="item in taskListStore.taskList?.items ?? []"
              :key="item.id"
              :class="`status-${item.status}`"
            >
              <span>{{ item.title }}</span>
              <strong>{{ taskStatusLabels[item.status] ?? item.status }}</strong>
            </li>
          </ol>
        </Transition>
      </aside>
    </Transition>

    <section
      v-if="hasMountedVisualization"
      class="visualization-result"
    >
      <header class="result-header">
        <div class="result-title">
          <strong>{{ workspaceStore.markdownHtmlVisualization.title }}</strong>
          <span>{{ workspaceStore.markdownHtmlVisualization.filename }}</span>
        </div>
        <div class="result-actions">
          <button
            type="button"
            :title="`保存到知识库 ${knowledgeSaveDirectory}`"
            @click="workspaceStore.saveMarkdownHtmlVisualizationToKnowledge"
          >
            <IcIcon name="download" :size="15" />
          </button>
          <button type="button" title="打开系统资源管理器保存" @click="workspaceStore.revealMarkdownHtmlVisualization">
            <IcIcon name="folder-open" :size="15" />
          </button>
          <button type="button" title="关闭" @click="workspaceStore.closeMarkdownHtmlVisualization">
            <IcIcon name="close" :size="15" />
          </button>
        </div>
      </header>
      <iframe
        class="result-frame"
        :src="workspaceStore.markdownHtmlVisualizationUrl"
        sandbox="allow-scripts allow-same-origin"
      ></iframe>
    </section>

    <section v-else class="visualization-empty">
      <IcIcon name="code" :size="28" />
      <strong>还没有生成 HTML 可视化</strong>
      <span>右键文件选择“HTML可视化”，或在本页选择文件后再一键可视化。</span>
    </section>

    <FloatingFileResourcePicker v-if="pickerOpen" @close="pickerOpen = false" />
  </section>
</template>

<style scoped>
.visualization-page {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-canvas-soft);
}

.visualization-toolbar,
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  min-width: 0;
  border-bottom: 0;
  background: var(--color-canvas);
}

.visualization-toolbar {
  min-height: 52px;
  padding: 0 var(--space-16);
}

.result-title strong,
.result-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-pill {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  flex-shrink: 0;
}

.mode-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-softer);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.mode-button {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 26px;
  padding: 0 var(--space-10);
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  outline: none;
  white-space: nowrap;
}

.mode-button:hover {
  color: var(--color-primary);
}

.mode-button.active {
  color: var(--color-primary);
}

.toolbar-actions button,
.preset-grid button,
.advanced-page-tabs button,
.result-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast);
}

.toolbar-actions > button {
  padding: 0 var(--space-10);
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.toolbar-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
  flex: 0 0 auto;
}

.selected-file-path {
  display: inline-block;
  width: min(32vw, 380px);
  min-width: 100px;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-actions > button.secondary-action {
  border-color: var(--color-border);
  background: transparent;
  color: var(--color-text);
}

.toolbar-actions > button.secondary-action.active,
.toolbar-actions > button.secondary-action:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.toolbar-actions > button.tool-button {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
}

.toolbar-actions > button.tool-button:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.toolbar-actions > button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.advanced-menu-wrap {
  position: relative;
  display: inline-flex;
}

.advanced-menu {
  position: absolute;
  top: calc(100% + var(--space-8));
  right: 0;
  z-index: 30;
  display: grid;
  gap: var(--space-12);
  width: 360px;
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.24);
  animation: advanced-menu-in 160ms ease-out;
}

.advanced-section {
  display: grid;
  gap: var(--space-8);
  min-width: 0;
}

.advanced-section-title {
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
}

.preset-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.advanced-page-tabs {
  display: inline-grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.preset-grid button.active,
.advanced-page-tabs button.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.option-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-12);
  min-width: 0;
}

.option-row label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.custom-requirement-field {
  display: grid;
  gap: var(--space-6);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.custom-requirement-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 68px;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-8);
  background: var(--color-canvas-soft);
  color: var(--color-text);
  font: inherit;
  line-height: 1.45;
}

.custom-requirement-field textarea:focus {
  border-color: var(--color-primary);
  outline: none;
}

.task-progress-card {
  position: absolute;
  top: calc(52px + var(--space-12));
  right: var(--space-16);
  z-index: 20;
  display: grid;
  gap: var(--space-8);
  width: min(340px, calc(100% - 32px));
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  color: var(--color-text);
}

.task-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  min-width: 0;
}

.task-progress-head div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.task-progress-head span,
.task-progress-card p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress-head span {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
}

.task-progress-head strong,
.task-progress-list strong {
  color: var(--color-primary);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
}

.task-progress-toggle {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast);
}

.task-progress-toggle[aria-expanded="true"] {
  color: var(--color-primary);
  transform: rotate(180deg);
}

.task-progress-bar {
  height: 3px;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.task-progress-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 220ms ease;
}

.task-progress-card p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.task-progress-list {
  display: grid;
  gap: var(--space-6);
  max-height: 180px;
  margin: 0;
  padding: var(--space-4) 0 0;
  overflow: auto;
  list-style: none;
}

.task-progress-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 26px;
  padding: 0 var(--space-8);
  border-left: 2px solid var(--color-border);
  background: var(--color-canvas-soft);
}

.task-progress-list li.status-completed {
  border-left-color: var(--color-success);
}

.task-progress-list li.status-in_progress {
  border-left-color: var(--color-primary);
}

.task-progress-list li.status-failed {
  border-left-color: var(--color-danger);
}

.task-progress-list span {
  overflow: hidden;
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress-float-enter-active,
.task-progress-float-leave-active,
.task-list-expand-enter-active,
.task-list-expand-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.task-progress-float-enter-from,
.task-progress-float-leave-to,
.task-list-expand-enter-from,
.task-list-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@keyframes advanced-menu-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.visualization-result {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  margin: var(--space-12);
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}

.result-header {
  min-height: 38px;
  padding: 0 var(--space-10);
}

.result-title {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.result-title strong {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.result-title span {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.result-actions {
  display: inline-flex;
  gap: var(--space-4);
  flex: 0 0 auto;
}

.result-actions button {
  width: 26px;
  padding: 0;
  color: var(--color-text-muted);
}

.result-actions button:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.result-frame {
  flex: 1;
  min-width: 0;
  min-height: 0;
  border: 0;
  background: white;
}

.visualization-empty {
  display: grid;
  place-items: center;
  align-content: center;
  gap: var(--space-8);
  min-width: 0;
  min-height: 0;
  color: var(--color-text-muted);
}

.visualization-empty strong {
  color: var(--color-text);
  font-size: calc(14px * var(--font-scale));
}

.visualization-empty span {
  font-size: calc(12px * var(--font-scale));
}

@media (max-width: 780px) {
  .visualization-toolbar {
    align-items: stretch;
    flex-direction: column;
    padding: var(--space-10);
  }

  .toolbar-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .advanced-menu-wrap {
    display: grid;
  }

  .advanced-menu {
    position: static;
    width: 100%;
    margin-top: var(--space-8);
  }

  .toolbar-actions > button {
    width: 100%;
  }
}
</style>
