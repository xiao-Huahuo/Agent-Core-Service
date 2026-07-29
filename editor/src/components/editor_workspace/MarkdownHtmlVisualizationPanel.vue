<!--
  Markdown HTML visualization panel.

  Usage:
  Mounts Agent-generated runtime HTML in an iframe and exposes save/reveal
  actions owned by the workspace store.
-->
<script setup lang="ts">
import { Download, FolderOpen, X } from 'lucide-vue-next'

import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
</script>

<template>
  <section
    v-if="workspaceStore.markdownHtmlVisualizationOpen && workspaceStore.markdownHtmlVisualization"
    class="markdown-html-visualization"
  >
    <header class="visualization-header">
      <div class="visualization-title">
        <strong>{{ workspaceStore.markdownHtmlVisualization.title }}</strong>
        <span>{{ workspaceStore.markdownHtmlVisualization.filename }}</span>
      </div>
      <div class="visualization-actions">
        <button type="button" title="保存到知识库" @click="workspaceStore.saveMarkdownHtmlVisualizationToKnowledge">
          <Download :size="15" />
        </button>
        <button type="button" title="在资源管理器中显示" @click="workspaceStore.revealMarkdownHtmlVisualization">
          <FolderOpen :size="15" />
        </button>
        <button type="button" title="关闭" @click="workspaceStore.closeMarkdownHtmlVisualization">
          <X :size="15" />
        </button>
      </div>
    </header>
    <iframe
      class="visualization-frame"
      :src="workspaceStore.markdownHtmlVisualizationUrl"
      sandbox="allow-scripts allow-same-origin"
    ></iframe>
  </section>
</template>

<style scoped>
.markdown-html-visualization {
  position: absolute;
  inset: 34px var(--space-10) var(--space-10);
  z-index: 20;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 0 8px 8px 8px;
  background: var(--color-canvas);
}

.visualization-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 36px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas-soft);
}

.visualization-title {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.visualization-title strong,
.visualization-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.visualization-title strong {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
}

.visualization-title span {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.visualization-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  flex: 0 0 auto;
}

.visualization-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast);
}

.visualization-actions button:hover {
  border-color: var(--color-border);
  background: var(--color-canvas);
  color: var(--color-text);
}

.visualization-frame {
  flex: 1;
  min-width: 0;
  min-height: 0;
  border: 0;
  background: white;
}
</style>
