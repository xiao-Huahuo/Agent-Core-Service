<!--
  文件树递归节点组件。
  使用 checkbox、label 与嵌套列表组成用户指定的文件树结构，同时把项目的选择、拖放、
  右键菜单和行内重命名事件原样转交给 FileTreePanel。
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import FavoriteButton from '@/components/common/FavoriteButton.vue'
import IcIcon from '@/components/common/IcIcon.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import { useSettingsStore } from '@/stores/settings'
import type { KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'TreeNode' })

/** 文件树状态列的全局显示设置，由顶部状态按钮统一切换。 */
const settingsStore = useSettingsStore()

/** 文件树节点及父级面板维护的交互状态。 */
const props = defineProps<{
  node: KnowledgeFileNode
  depth: number
  expandedPaths: Set<string>
  selectedPath: string
  selectedPaths: Set<string>
  dirtyPaths: Set<string>
  editingPath: string
  editingValue: string
}>()

/** 向文件树面板转交节点交互，不在递归节点内复制业务状态。 */
const emit = defineEmits<{
  select: [node: KnowledgeFileNode, event?: MouseEvent | KeyboardEvent]
  dropFiles: [node: KnowledgeFileNode, files: File[]]
  dropNodes: [node: KnowledgeFileNode, paths: string[]]
  nodeDragStart: [node: KnowledgeFileNode, event: DragEvent]
  contextMenu: [node: KnowledgeFileNode, event: MouseEvent]
  ingest: [node: KnowledgeFileNode]
  editInput: [value: string]
  editCommit: [value: string]
  editCancel: []
}>()

/** 当前节点的行内重命名输入框。 */
const inlineInput = ref<HTMLInputElement | null>(null)
/** 当前节点是否正在接收拖放。 */
const dragOver = ref(false)
/** 文件夹是否由父级状态标记为展开。 */
const isExpanded = computed(() => props.expandedPaths.has(props.node.path))
/** 当前节点是否属于单选或多选集合。 */
const isSelected = computed(
  () => props.selectedPath === props.node.path || props.selectedPaths.has(props.node.path),
)
/** 为 label 与 checkbox 生成稳定且合法的关联标识。 */
const folderToggleId = computed(
  () => `tree-node-${(props.node.path || props.node.name).replace(/[^a-zA-Z0-9_-]/g, '-')}-toggle`,
)
/** 索引状态的语义样式。 */
const indexStatusClass = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return 'indexed'
  if (props.node.indexStatus === 'ignored') return 'ignored'
  if (props.node.indexStatus === 'failed') return 'failed'
  return 'dirty'
})
/** 索引状态的悬停说明。 */
const indexStatusTitle = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return '已进入向量库'
  if (props.node.indexStatus === 'ignored') return '已屏蔽, 不进入向量库'
  if (props.node.indexStatus === 'failed') return '入库失败'
  return '未进入向量库'
})
/** 索引状态对应的项目图标。 */
const indexStatusIcon = computed(() => {
  if (props.node.indexStatus === 'indexed' || props.node.indexStatus === 'clean') return 'check-circle'
  if (props.node.indexStatus === 'ignored') return 'block'
  return 'error-outline'
})
/** 图谱状态的语义样式。 */
const graphStatusClass = computed(() => {
  if (props.node.graphStatus === 'graphed') return 'graphed'
  if (props.node.graphStatus === 'ignored') return 'ignored'
  return 'dirty'
})
/** 图谱状态的悬停说明。 */
const graphStatusTitle = computed(() => {
  if (props.node.graphStatus === 'graphed') return '已入图谱'
  if (props.node.graphStatus === 'ignored') return '已屏蔽, 不进入图谱'
  return '未入图谱'
})
/** 图谱状态对应的项目图标。 */
const graphStatusIcon = computed(() => {
  if (props.node.graphStatus === 'graphed') return 'hub'
  if (props.node.graphStatus === 'ignored') return 'block'
  return 'git'
})

/** 节点进入重命名状态时自动聚焦并选中原名称。 */
watch(
  () => props.editingPath,
  () => {
    if (props.editingPath !== props.node.path) return
    void nextTick(() => {
      inlineInput.value?.focus()
      inlineInput.value?.select()
    })
  },
  { immediate: true },
)

/** 把文件行或键盘选择交给父级面板。 */
function handleRowSelect(event?: MouseEvent | KeyboardEvent) {
  emit('select', props.node, event)
}

/** checkbox 改变时由父级统一更新文件夹展开集合。 */
function handleFolderToggle() {
  emit('select', props.node)
}

/** 允许当前节点成为文件或树节点的拖放目标。 */
function handleRowDragover(event: DragEvent) {
  event.preventDefault()
  dragOver.value = true
}

/** 指针真正离开整行时清除拖放提示。 */
function handleRowDragLeave(event: DragEvent) {
  const row = event.currentTarget as HTMLElement | null
  const destination = event.relatedTarget as HTMLElement | null
  if (row && destination && row.contains(destination)) return
  dragOver.value = false
}

/** 区分系统文件与文件树节点，并转交对应的拖放事件。 */
function handleRowDrop(event: DragEvent) {
  event.preventDefault()
  event.stopPropagation()
  dragOver.value = false

  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length > 0) {
    emit('dropFiles', props.node, files)
    return
  }

  const payload = event.dataTransfer?.getData('application/x-metaweave-tree-paths') ?? ''
  if (!payload) return

  try {
    emit('dropNodes', props.node, JSON.parse(payload) as string[])
  } catch {
    // 忽略文件树之外来源不明且格式无效的拖放数据。
  }
}
</script>

<template>
  <li class="tree-item" :class="{ 'drag-over': dragOver }">
    <template v-if="node.isDir">
      <input
        :id="folderToggleId"
        type="checkbox"
        class="tree-toggle"
        :checked="isExpanded"
        @change="handleFolderToggle"
      />
      <label
        :for="folderToggleId"
        class="tree-label"
        :class="{ 'is-selected': isSelected }"
        role="button"
        tabindex="0"
        draggable="true"
        @dragstart="emit('nodeDragStart', node, $event)"
        @dragover="handleRowDragover"
        @dragleave="handleRowDragLeave"
        @drop="handleRowDrop"
        @keydown.enter="handleRowSelect($event)"
        @contextmenu.prevent.stop="emit('contextMenu', node, $event)"
      >
        <img
          class="icon material-file-icon"
          :src="materialFileIconForNode(node, isExpanded).src"
          alt=""
          aria-hidden="true"
        />
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
        <span v-else class="tree-name">{{ node.name }}</span>
        <span
          v-if="settingsStore.showIndexColumn || settingsStore.showGraphColumn"
          class="node-status-cluster"
        >
          <IcIcon
            v-if="!node.isDir && settingsStore.showIndexColumn"
            :name="indexStatusIcon"
            class="node-index-dot"
            :class="indexStatusClass"
            :size="13"
            :title="indexStatusTitle"
          />
          <span v-else-if="settingsStore.showIndexColumn" class="node-status-placeholder" />
          <IcIcon
            v-if="!node.isDir && settingsStore.showGraphColumn"
            :name="graphStatusIcon"
            class="node-graph-dot"
            :class="graphStatusClass"
            :size="13"
            :title="graphStatusTitle"
          />
          <span v-else-if="settingsStore.showGraphColumn" class="node-status-placeholder" />
        </span>
        <FavoriteButton
          v-if="settingsStore.showFavoriteColumn"
          target-type="knowledge_path"
          :target-id="node.path"
          :size="13"
        />
      </label>

      <div class="tree-children-wrapper">
        <ul class="tree-children">
          <TreeNode
            v-for="child in node.children"
            :key="child.path"
            :node="child"
            :depth="depth + 1"
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
      </div>
    </template>

    <div
      v-else
      class="file-item"
      :class="{ 'is-selected': isSelected }"
      role="button"
      tabindex="0"
      draggable="true"
      @dragstart="emit('nodeDragStart', node, $event)"
      @dragover="handleRowDragover"
      @dragleave="handleRowDragLeave"
      @drop="handleRowDrop"
      @click="handleRowSelect($event)"
      @keydown.enter="handleRowSelect($event)"
      @contextmenu.prevent.stop="emit('contextMenu', node, $event)"
    >
      <img
        class="icon material-file-icon"
        :src="materialFileIconForNode(node).src"
        alt=""
        aria-hidden="true"
      />
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
      <span v-else class="tree-name">{{ node.name }}</span>
      <span
        v-if="settingsStore.showIndexColumn || settingsStore.showGraphColumn"
        class="node-status-cluster"
      >
        <IcIcon
          v-if="settingsStore.showIndexColumn"
          :name="indexStatusIcon"
          class="node-index-dot"
          :class="indexStatusClass"
          :size="13"
          :title="indexStatusTitle"
        />
        <IcIcon
          v-if="settingsStore.showGraphColumn"
          :name="graphStatusIcon"
          class="node-graph-dot"
          :class="graphStatusClass"
          :size="13"
          :title="graphStatusTitle"
        />
      </span>
      <FavoriteButton
        v-if="settingsStore.showFavoriteColumn"
        target-type="knowledge_path"
        :target-id="node.path"
        :size="13"
      />
    </div>
  </li>
</template>

<style scoped>
ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.tree-children {
  margin-left: 11px;
  padding-left: 11px;
  border-left: 1px solid var(--color-border-subtle, var(--color-border));
}

.tree-item {
  position: relative;
  margin-top: 4px;
}

.tree-children > .tree-item::before {
  content: "";
  position: absolute;
  left: -11px;
  top: 14px;
  width: 11px;
  height: 1px;
  background-color: var(--color-border-subtle, var(--color-border));
}

.tree-label,
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 28px;
  padding: 4px 8px;
  border-radius: 4px;
  box-sizing: border-box;
  cursor: pointer;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: 14px;
  text-decoration: none;
  user-select: none;
  transition: background-color 0.2s;
}

.tree-label:hover,
.file-item:hover,
.drag-over > .tree-label,
.file-item.drag-over {
  background-color: var(--color-surface-raised);
}

.is-selected {
  background-color: var(--color-surface-raised);
  color: var(--color-text);
  font-weight: 500;
}

.icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.material-file-icon {
  display: block;
  object-fit: contain;
}

.tree-toggle {
  display: none;
}

.tree-children-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease-in-out;
}

.tree-children {
  overflow: hidden;
}

.tree-toggle:checked ~ .tree-children-wrapper {
  grid-template-rows: 1fr;
}

.tree-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.node-status-cluster {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
}

.node-index-dot,
.node-graph-dot,
.node-status-placeholder {
  flex: 0 0 16px;
  width: 16px;
  color: var(--color-text-muted);
}

.node-index-dot.indexed,
.node-graph-dot.graphed {
  color: var(--color-primary);
}

.node-index-dot.failed,
.node-index-dot.dirty,
.node-graph-dot.dirty {
  color: var(--color-danger);
}

.node-index-dot.ignored,
.node-graph-dot.ignored {
  color: var(--color-text-muted);
}

.node-status-placeholder {
  display: block;
  height: 1px;
}

.node-editor {
  flex: 1;
  min-width: 0;
  height: 22px;
  padding: 0 4px;
  border: 1px solid var(--color-primary);
  border-radius: 4px;
  outline: none;
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
}
</style>
