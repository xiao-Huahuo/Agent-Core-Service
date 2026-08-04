<!--
  Recursive file tree node.

  Usage:
  Used by FileTreePanel to render directories and files without noisy status
  badges, keeping the tree focused on navigation.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  Ban,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  GitBranch,
  Network,
} from 'lucide-vue-next'

import FavoriteButton from '@/components/common/FavoriteButton.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { KnowledgeFileNode } from '@/types/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useGitStore } from '@/stores/git'

defineOptions({ name: 'TreeNode' })

const settingsStore = useSettingsStore()
const gitStore = useGitStore()

const statusWidth = computed(() => {
  const showIndex = settingsStore.showIndexColumn
  const showGraph = settingsStore.showGraphColumn
  if (showIndex && showGraph) return '58px'
  if (showIndex || showGraph) return '34px'
  return '8px'
})
const favoriteWidth = computed(() => settingsStore.showFavoriteColumn ? '24px' : '0px')

const props = defineProps<{
  node: KnowledgeFileNode
  depth: number
  expandedPaths: Set<string>
  selectedPath: string
  selectedPaths: Set<string>
  dirtyPaths: Set<string>
  editingPath: string
  editingValue: string
  staggerIndex?: number
}>()

const emit = defineEmits<{
  select: [node: KnowledgeFileNode, event: MouseEvent | KeyboardEvent]
  dropFiles: [node: KnowledgeFileNode, files: File[]]
  dropNodes: [node: KnowledgeFileNode, paths: string[]]
  nodeDragStart: [node: KnowledgeFileNode, event: DragEvent]
  contextMenu: [node: KnowledgeFileNode, event: MouseEvent]
  ingest: [node: KnowledgeFileNode]
  editInput: [value: string]
  editCommit: [value: string]
  editCancel: []
}>()

const inlineInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

const materialIcon = computed(() => materialFileIconForNode(props.node, props.node.isDir && props.expandedPaths.has(props.node.path)))
const gitStatusClass = computed(() => {
  return gitStore.statusClassForPath(props.node.path, props.node.isDir)
})

const indexStatusClass = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return 'indexed'
  if (props.node.indexStatus === 'ignored') return 'ignored'
  if (props.node.indexStatus === 'failed') return 'failed'
  return 'dirty'
})

const indexStatusTitle = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return '已进入向量库'
  if (props.node.indexStatus === 'ignored') return '已屏蔽, 不进入向量库'
  if (props.node.indexStatus === 'failed') return '入库失败'
  return '未进入向量库'
})

const indexStatusIcon = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return CircleCheck
  if (props.node.indexStatus === 'ignored') return Ban
  return CircleAlert
})

const graphStatusClass = computed(() => {
  if (props.node.graphStatus === 'graphed') return 'graphed'
  if (props.node.graphStatus === 'ignored') return 'ignored'
  return 'dirty'
})

const graphStatusTitle = computed(() => {
  if (props.node.graphStatus === 'graphed') return '已入图谱'
  if (props.node.graphStatus === 'ignored') return '已屏蔽, 不进入图谱'
  return '未入图谱'
})

const graphStatusIcon = computed(() => {
  if (props.node.graphStatus === 'graphed') return Network
  if (props.node.graphStatus === 'ignored') return Ban
  return GitBranch
})

watch(
  () => props.editingPath,
  () => {
    if (props.editingPath !== props.node.path) {
      return
    }
    void nextTick(() => {
      inlineInput.value?.focus()
      inlineInput.value?.select()
    })
  },
  { immediate: true },
)

function handleRowDragover(event: DragEvent) {
  event.preventDefault()
  dragOver.value = true
}

function collapseEnter(el: Element) {
  if (!(el instanceof HTMLElement)) return
  el.style.height = '0px'
  el.style.overflow = 'hidden'
  requestAnimationFrame(() => {
    const height = el.scrollHeight
    el.style.height = height + 'px'
  })
}

function collapseAfterEnter(el: Element) {
  if (!(el instanceof HTMLElement)) return
  el.style.height = ''
  el.style.overflow = ''
}

function collapseLeave(el: Element) {
  if (!(el instanceof HTMLElement)) return
  el.style.height = el.scrollHeight + 'px'
  el.style.overflow = 'hidden'
  requestAnimationFrame(() => {
    el.style.height = '0px'
  })
}

function collapseAfterLeave(el: Element) {
  if (!(el instanceof HTMLElement)) return
  el.style.height = ''
  el.style.overflow = ''
}

function handleRowDragLeave(event: DragEvent) {
  const el = event.currentTarget as HTMLElement | null
  const related = event.relatedTarget as HTMLElement | null
  if (el && related && el.contains(related)) return
  dragOver.value = false
}

function handleRowDrop(event: DragEvent) {
  event.preventDefault()
  event.stopPropagation()
  dragOver.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length > 0) {
    emit('dropFiles', props.node, files)
    return
  }
  const rawPaths = event.dataTransfer?.getData('application/x-metaweave-tree-paths') ?? ''
  if (!rawPaths) {
    return
  }
  try {
    const paths = JSON.parse(rawPaths) as string[]
    emit('dropNodes', props.node, paths)
  } catch {
    // Ignore malformed drag payloads from outside the file tree.
  }
}
</script>

<template>
  <li :style="{ '--stagger': staggerIndex ?? 0 }">
    <div
      class="tree-row"
      :class="[
        gitStatusClass,
        { selected: selectedPath === node.path || selectedPaths.has(node.path), 'drag-over': dragOver },
      ]"
      :style="{ paddingLeft: `${depth * 14 + 8}px`, '--status-width': statusWidth, '--favorite-width': favoriteWidth }"
      role="button"
      tabindex="0"
      draggable="true"
      @dragstart="emit('nodeDragStart', node, $event)"
      @dragover="handleRowDragover"
      @dragleave="handleRowDragLeave"
      @drop="handleRowDrop"
      @click="emit('select', node, $event)"
      @keydown.enter="emit('select', node, $event)"
      @contextmenu.prevent.stop="emit('contextMenu', node, $event)"
    >
      <ChevronRight v-if="node.isDir" :size="14" class="chevron" :class="{ expanded: expandedPaths.has(node.path) }" />
      <span v-else class="spacer"></span>
      <img class="material-file-icon" :src="materialIcon.src" :alt="materialIcon.alt" aria-hidden="true" />
      <input
        v-if="editingPath === node.path"
        ref="inlineInput"
        class="node-editor"
        :value="editingValue"
        @click.stop
        @input="emit('editInput', ($event.target as HTMLInputElement).value)"
        @blur="emit('editCommit', editingValue)"
        @keydown.enter.prevent.stop="emit('editCommit', editingValue)"
        @keydown.esc.prevent.stop="emit('editCancel')"
      />
      <span v-else class="node-name" :class="gitStatusClass">{{ node.name }}</span>
      <span class="node-status-cluster">
        <i class="node-dirty-dot" :class="{ show: dirtyPaths.has(node.path) }"></i>
        <component
          v-if="!node.isDir && settingsStore.showIndexColumn"
          :is="indexStatusIcon"
          class="node-index-dot"
          :class="indexStatusClass"
          :size="13"
          :title="indexStatusTitle"
        />
        <span v-if="node.isDir && settingsStore.showIndexColumn" class="node-index-placeholder"></span>
        <component
          v-if="!node.isDir && settingsStore.showGraphColumn"
          :is="graphStatusIcon"
          class="node-graph-dot"
          :class="graphStatusClass"
          :size="13"
          :title="graphStatusTitle"
        />
        <span v-if="node.isDir && settingsStore.showGraphColumn" class="node-index-placeholder"></span>
      </span>
      <FavoriteButton
        v-if="settingsStore.showFavoriteColumn"
        target-type="knowledge_path"
        :target-id="node.path"
        :size="13"
      />
    </div>
    <Transition
      name="tree-collapse"
      @enter="collapseEnter"
      @after-enter="collapseAfterEnter"
      @leave="collapseLeave"
      @after-leave="collapseAfterLeave"
    >
      <ul v-if="node.isDir && expandedPaths.has(node.path) && node.children" class="tree-children">
        <TreeNode
        v-for="(child, childIndex) in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :stagger-index="(staggerIndex ?? 0) + childIndex + 1"
        :expanded-paths="expandedPaths"
        :selected-path="selectedPath"
        :selected-paths="selectedPaths"
        :dirty-paths="dirtyPaths"
        :editing-path="editingPath"
        :editing-value="editingValue"
        @select="(targetNode, event) => emit('select', targetNode, event)"
        @drop-files="(targetNode, files) => emit('dropFiles', targetNode, files)"
        @drop-nodes="(targetNode, paths) => emit('dropNodes', targetNode, paths)"
        @node-drag-start="(targetNode, event) => emit('nodeDragStart', targetNode, event)"
        @context-menu="(targetNode, event) => emit('contextMenu', targetNode, event)"
        @ingest="(targetNode) => emit('ingest', targetNode)"
        @edit-input="emit('editInput', $event)"
        @edit-commit="emit('editCommit', $event)"
        @edit-cancel="emit('editCancel')"
      />
      </ul>
    </Transition>
  </li>
</template>

<style scoped>
.tree-row {
  position: relative;
  display: grid;
  grid-template-columns: 14px 16px minmax(0, 1fr) var(--status-width, 58px) var(--favorite-width, 24px);
  animation: tree-node-enter 0.25s ease-out both;
  animation-delay: calc(var(--stagger, 0) * 40ms);
  align-items: center;
  isolation: isolate;
  gap: var(--space-6);
  width: 100%;
  min-height: 30px;
  padding-right: var(--space-6);
  border: 1px solid transparent;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
  overflow: hidden;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.tree-row > * {
  position: relative;
  z-index: 1;
}

.tree-row:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.tree-row.selected {
  background: var(--color-primary-soft);
  color: var(--color-text);
}

.tree-row.selected::before {
  position: absolute;
  inset: 0;
  z-index: 0;
  background: linear-gradient(90deg, var(--color-primary-soft), transparent 68%);
  content: "";
  animation: tree-selection-slide 150ms ease-out;
}

.chevron {
  transition: transform 200ms ease;
}

.chevron.expanded {
  transform: rotate(90deg);
}

.spacer {
  width: 14px;
}

.tree-children {
  margin: 0;
  padding: 0;
  list-style: none;
  overflow: hidden;
}

.tree-collapse-enter-active,
.tree-collapse-leave-active {
  overflow: hidden;
  transition: height 200ms ease;
}

.node-name {
  overflow: hidden;
  font-size: calc(13px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-name.git-modified {
  color: var(--color-git-modified);
}

.node-name.git-added {
  color: var(--color-git-added);
}

.node-name.git-untracked {
  color: var(--color-git-untracked);
}

.node-name.git-conflicted {
  color: var(--color-danger);
}

.node-name.git-deleted {
  color: var(--color-git-deleted);
}

.node-name.git-renamed {
  color: var(--color-git-renamed);
}

.node-name.git-ignored {
  color: var(--color-git-ignored);
}

.tree-row.git-modified .node-name,
.tree-row .node-name.git-modified {
  color: var(--color-git-modified);
}

.tree-row.git-added .node-name,
.tree-row .node-name.git-added {
  color: var(--color-git-added);
}

.tree-row.git-untracked .node-name,
.tree-row .node-name.git-untracked {
  color: var(--color-git-untracked);
}

.tree-row.git-conflicted .node-name,
.tree-row .node-name.git-conflicted {
  color: var(--color-danger);
}

.tree-row.git-deleted .node-name,
.tree-row .node-name.git-deleted {
  color: var(--color-git-deleted);
}

.tree-row.git-renamed .node-name,
.tree-row .node-name.git-renamed {
  color: var(--color-git-renamed);
}

.tree-row.git-ignored .node-name,
.tree-row .node-name.git-ignored {
  color: var(--color-git-ignored);
}

.node-editor {
  width: 100%;
  min-width: 0;
  height: 22px;
  padding: 0 var(--space-4);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  outline: none;
}

.node-status-cluster {
  display: inline-grid;
  grid-template-columns: 8px 16px 16px;
  align-items: center;
  justify-content: end;
  gap: 8px;
  min-width: var(--status-width, 58px);
  padding-left: 8px;
}

.node-dirty-dot {
  justify-self: center;
  align-self: center;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
  visibility: hidden;
}

.node-dirty-dot.show {
  visibility: visible;
}

.node-index-dot {
  justify-self: center;
  color: var(--color-text-muted);
}

.node-index-placeholder {
  display: block;
  width: 16px;
  height: 1px;
}

.node-index-dot.indexed {
  color: var(--color-primary);
}

.node-index-dot.ignored {
  color: var(--color-text-muted);
}

.node-index-dot.failed {
  color: var(--color-danger);
}

.node-graph-dot {
  justify-self: center;
  color: var(--color-text-muted);
}

.node-graph-dot.graphed {
  color: var(--color-primary);
}

.node-graph-dot.dirty {
  color: var(--color-danger);
}

.node-graph-dot.ignored {
  color: var(--color-text-muted);
}

.material-file-icon {
  display: block;
  width: 16px;
  height: 16px;
  object-fit: contain;
  pointer-events: none;
}

.tree-row.drag-over {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-primary) 50%, transparent);
}

@keyframes tree-selection-slide {
  from {
    transform: translateX(-18px);
    opacity: 0.35;
  }

  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes tree-node-enter {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

</style>
