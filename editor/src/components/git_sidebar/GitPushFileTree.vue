<!--
  Git push file-tree renderer.

  Usage:
  Recursively renders only files present in the unpushed commit range. Directory
  rows can be collapsed without changing repository state.
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { GitPushTreeNode } from '@/components/git_sidebar/gitPushTree'

defineOptions({ name: 'GitPushFileTree' })

withDefaults(defineProps<{
  /** Nodes at the current directory level. */
  nodes: GitPushTreeNode[]
  /** Current nesting depth used for IDE-style indentation. */
  level?: number
}>(), {
  level: 0,
})

/** Directory paths collapsed by the user in this renderer level. */
const collapsedPaths = ref<Set<string>>(new Set())

/** Toggle one directory without mutating the received tree. */
function toggleDirectory(path: string): void {
  const next = new Set(collapsedPaths.value)
  if (next.has(path)) next.delete(path)
  else next.add(path)
  collapsedPaths.value = next
}
</script>

<template>
  <ul class="push-file-tree" role="tree">
    <li v-for="node in nodes" :key="node.path" role="treeitem">
      <button
        v-if="node.directory"
        class="tree-row directory-row"
        type="button"
        :style="{ paddingLeft: `${level * 14 + 4}px` }"
        :aria-expanded="!collapsedPaths.has(node.path)"
        @click="toggleDirectory(node.path)"
      >
        <IcIcon name="chevron-right" :size="13" :class="{ expanded: !collapsedPaths.has(node.path) }" />
        <img
          :src="materialFileIconForNode({ name: node.name, path: node.path, isDir: true }).src"
          alt=""
        />
        <span>{{ node.name }}</span>
      </button>
      <div
        v-else
        class="tree-row file-row"
        :style="{ paddingLeft: `${level * 14 + 21}px` }"
      >
        <img
          :src="materialFileIconForNode({ name: node.name, path: node.path, isDir: false }).src"
          alt=""
        />
        <span>{{ node.name }}</span>
        <code>{{ node.status }}</code>
      </div>
      <GitPushFileTree
        v-if="node.directory && !collapsedPaths.has(node.path)"
        :nodes="node.children"
        :level="level + 1"
      />
    </li>
  </ul>
</template>

<style scoped>
.push-file-tree {
  margin: 0;
  padding: 0;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  list-style: none;
}

.tree-row {
  display: grid;
  grid-template-columns: 14px 16px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  min-height: 28px;
  padding-right: var(--space-4);
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  text-align: left;
}

.tree-row:hover {
  background: var(--color-selection-blue-soft);
}

.directory-row {
  cursor: pointer;
}

.directory-row svg {
  color: var(--color-text-muted);
  transition: transform 160ms ease;
}

.directory-row svg.expanded {
  transform: rotate(90deg);
}

.tree-row img {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

.tree-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-row {
  grid-template-columns: 16px minmax(0, 1fr) auto;
}

.file-row code {
  color: var(--color-text-muted);
  font: inherit;
}

@media (prefers-reduced-motion: reduce) {
  .directory-row svg {
    transition: none;
  }
}
</style>
