<!--
  Workspace embedded knowledge graph pane.

  Usage:
  Renders the reusable KnowledgeGraphCanvas inside the editor center column.
  This component adapts workspace store data to graph data and emits node-open
  events upward; it intentionally does not own route navigation or file opening.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Crosshair, RotateCcw } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import KnowledgeGraphCanvas from '@/components/knowledge_graph/KnowledgeGraphCanvas.vue'
import { buildFileTreeGraph } from '@/components/knowledge_graph/fileTreeGraphAdapter'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

const emit = defineEmits<{
  'open-node': [node: KnowledgeGraphNodeEvent]
}>()

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const { tree, treeLoading } = storeToRefs(workspaceStore)
const graphCanvasRef = ref<InstanceType<typeof KnowledgeGraphCanvas> | null>(null)
const selectedNode = ref<KnowledgeGraphNodeEvent | null>(null)

function basename(path: string): string {
  return path.replace(/[\\/]+$/g, '').split(/[\\/]/).filter(Boolean).pop() ?? 'Knowledge Root'
}

const knowledgeTitle = computed(() => {
  const libraryName = settingsStore.activeKnowledgeLibrary?.name?.trim()
  return libraryName || basename(settingsStore.profile.knowledgeDir) || 'Knowledge Root'
})

const graphModel = computed(() => buildFileTreeGraph(tree.value, { rootLabel: knowledgeTitle.value }))

const graphStats = computed(() => ({
  nodes: graphModel.value.nodes.length,
  links: graphModel.value.links.length,
}))

function handleNodeSelect(node: KnowledgeGraphNodeEvent) {
  selectedNode.value = node
  emit('open-node', node)
}

onMounted(() => {
  if (settingsStore.profile.userId && tree.value.length === 0) {
    void workspaceStore.loadKnowledgeTree()
  }
})
</script>

<template>
  <section class="graph-pane">
    <header class="graph-toolbar">
      <div class="graph-title">
        <span class="eyebrow mono">knowledge graph</span>
        <strong>{{ knowledgeTitle }}</strong>
      </div>
      <div class="graph-actions">
        <span class="graph-stat mono">{{ graphStats.nodes }} nodes / {{ graphStats.links }} links</span>
        <button class="graph-action" type="button" title="Fit view" @click="graphCanvasRef?.fitToView()">
          <Crosshair :size="15" />
          <span>Fit</span>
        </button>
        <button class="graph-action" type="button" title="Reheat layout" @click="graphCanvasRef?.reheatLayout()">
          <RotateCcw :size="15" />
          <span>Layout</span>
        </button>
      </div>
    </header>

    <KnowledgeGraphCanvas
      ref="graphCanvasRef"
      class="embedded-graph"
      :model="graphModel"
      :selected-node-id="selectedNode?.id ?? ''"
      @node-open="emit('open-node', $event)"
      @node-select="handleNodeSelect"
    />

    <footer class="graph-status">
      <span v-if="treeLoading" class="mono">loading tree...</span>
      <span v-else-if="selectedNode" class="mono">{{ selectedNode.path || selectedNode.label }}</span>
      <span v-else class="mono">click a node to open it in the editor</span>
    </footer>
  </section>
</template>

<style scoped>
.graph-pane {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-canvas-soft);
}

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  min-height: 38px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
}

.graph-title {
  min-width: 0;
}

.graph-title strong {
  display: block;
  overflow: hidden;
  color: var(--color-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.eyebrow {
  display: block;
  color: var(--color-text-muted);
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.graph-actions {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-shrink: 0;
}

.graph-stat {
  color: var(--color-text-muted);
  font-size: 10px;
}

.graph-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 24px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 11px;
}

.graph-action:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-text);
}

.embedded-graph {
  min-width: 0;
  min-height: 0;
}

.graph-status {
  display: flex;
  align-items: center;
  min-height: 24px;
  padding: 0 var(--space-10);
  border-top: 1px solid var(--color-border);
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font-size: 10px;
  overflow: hidden;
}

.graph-status span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
