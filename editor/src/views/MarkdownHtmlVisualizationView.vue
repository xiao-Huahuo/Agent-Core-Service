<!--
  Markdown HTML visualization workspace page.

  Usage:
  Provides a visible page for configuring the Agent document visualization
  workflow and for mounting the generated runtime HTML.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, Download, FileCode, FolderOpen, Play, SlidersHorizontal, X } from 'lucide-vue-next'

import FloatingFileResourcePicker from '@/components/editor_workspace/FloatingFileResourcePicker.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { MarkdownHtmlVisualizationOptions } from '@/types/knowledge'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const pickerOpen = ref(false)
const advancedOptionsOpen = ref(false)

const visualizationOptions: Array<{ key: keyof MarkdownHtmlVisualizationOptions; label: string }> = [
  { key: 'strongMotion', label: '强动效' },
  { key: 'shadow', label: '阴影' },
  { key: 'rounded', label: '圆角' },
  { key: 'emoji', label: 'emoji' },
]

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

function setMode(mode: 'structure' | 'insight') {
  workspaceStore.setMarkdownHtmlVisualizationMode(mode)
}

function setOption(key: keyof MarkdownHtmlVisualizationOptions, event: Event) {
  workspaceStore.setMarkdownHtmlVisualizationOption(key, (event.target as HTMLInputElement).checked)
}

function startVisualization() {
  void workspaceStore.startMarkdownHtmlVisualization()
}
</script>

<template>
  <section class="visualization-page">
    <header class="visualization-toolbar">
      <div class="toolbar-title">
        <FileCode :size="18" />
        <div>
          <h1>MD-HTML</h1>
          <p>{{ selectedDocumentLabel }}</p>
        </div>
      </div>
      <div class="toolbar-actions">
        <button type="button" class="secondary-action" @click="pickerOpen = true">
          <FolderOpen :size="15" />
          <span>选择文件</span>
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
            <SlidersHorizontal :size="15" />
            <span>高级选项</span>
            <ChevronDown :size="14" />
          </button>
          <div v-if="advancedOptionsOpen" class="advanced-menu" role="menu">
            <div class="mode-switch" aria-label="HTML 可视化模式">
              <button
                type="button"
                :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'structure' }"
                @click="setMode('structure')"
              >
                原结构模式
              </button>
              <button
                type="button"
                :class="{ active: workspaceStore.markdownHtmlVisualizationMode === 'insight' }"
                @click="setMode('insight')"
              >
                AI提炼模式
              </button>
            </div>
            <div class="option-row">
              <label v-for="option in visualizationOptions" :key="option.key">
                <input
                  type="checkbox"
                  :checked="workspaceStore.markdownHtmlVisualizationOptions[option.key]"
                  @change="setOption(option.key, $event)"
                />
                <span>{{ option.label }}</span>
              </label>
            </div>
          </div>
        </div>
        <button
          type="button"
          :disabled="!workspaceStore.selectedNode || workspaceStore.selectedNode.isDir || workspaceStore.refreshing"
          @click="startVisualization"
        >
          <Play :size="15" />
          <span>一键可视化</span>
        </button>
      </div>
    </header>

    <section
      v-if="workspaceStore.markdownHtmlVisualizationOpen && workspaceStore.markdownHtmlVisualization"
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
            <Download :size="15" />
          </button>
          <button type="button" title="打开系统资源管理器保存" @click="workspaceStore.revealMarkdownHtmlVisualization">
            <FolderOpen :size="15" />
          </button>
          <button type="button" title="关闭" @click="workspaceStore.closeMarkdownHtmlVisualization">
            <X :size="15" />
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
      <FileCode :size="28" />
      <strong>还没有生成 HTML 可视化</strong>
      <span>右键文件选择“HTML可视化”，或在本页选择文件后再一键可视化。</span>
    </section>

    <FloatingFileResourcePicker v-if="pickerOpen" @close="pickerOpen = false" />
  </section>
</template>

<style scoped>
.visualization-page {
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
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
}

.visualization-toolbar {
  min-height: 52px;
  padding: 0 var(--space-16);
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  min-width: 0;
}

.toolbar-title h1,
.toolbar-title p,
.result-title strong,
.result-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-title h1 {
  margin: 0;
  color: var(--color-text);
  font-size: calc(15px * var(--font-scale));
  font-weight: 650;
}

.toolbar-title p {
  margin: 2px 0 0;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.toolbar-actions button,
.mode-switch button,
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

.toolbar-actions button {
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

.toolbar-actions button.secondary-action {
  border-color: var(--color-border);
  background: transparent;
  color: var(--color-text);
}

.toolbar-actions button.secondary-action.active,
.toolbar-actions button.secondary-action:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.toolbar-actions button:disabled {
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
  width: 312px;
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.24);
  animation: advanced-menu-in 160ms ease-out;
}

.mode-switch {
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  min-width: 220px;
}

.mode-switch button.active {
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
  border: 1px solid var(--color-border);
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

  .mode-switch,
  .toolbar-actions button {
    width: 100%;
  }
}
</style>
