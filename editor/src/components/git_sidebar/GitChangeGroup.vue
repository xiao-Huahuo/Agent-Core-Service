<!--
  Git change group.

  Usage:
  Renders one collapsible "Changes" or "Unversioned files" section with group
  selection and per-file selection shared by either Git sidebar placement.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'

import GitCheckbox from '@/components/git_sidebar/GitCheckbox.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { GitFileChange } from '@/api/git'

defineOptions({ name: 'GitChangeGroup' })

const props = defineProps<{
  title: string
  files: GitFileChange[]
  expanded: boolean
  selectedPaths: Set<string>
}>()

const emit = defineEmits<{
  toggleExpanded: []
  toggleAll: [selected: boolean]
  togglePath: [path: string]
}>()

const allSelected = computed(() => (
  props.files.length > 0 && props.files.every((item) => props.selectedPaths.has(item.path))
))

function statusLabel(item: GitFileChange): string {
  if (item.state === 'modified') return 'M'
  if (item.state === 'added') return 'A'
  if (item.state === 'deleted') return 'D'
  if (item.state === 'renamed') return 'R'
  if (item.state === 'conflicted') return '!'
  return '?'
}
</script>

<template>
  <section class="change-group">
    <div class="group-header">
      <GitCheckbox
        :checked="allSelected"
        :label="`选择全部${title}`"
        @change="emit('toggleAll', $event)"
      />
      <button
        class="group-toggle"
        type="button"
        :aria-expanded="expanded"
        @click="emit('toggleExpanded')"
      >
        <ChevronRight :size="14" :class="{ expanded }" />
        <span>{{ title }}</span>
      </button>
      <span class="group-count">{{ files.length }} 个文件</span>
    </div>

    <Transition name="group-collapse">
      <ul v-if="expanded" class="change-list">
        <li v-for="item in files" :key="item.path" class="change-row">
          <GitCheckbox
            :checked="selectedPaths.has(item.path)"
            :label="`选择 ${item.path}`"
            @change="emit('togglePath', item.path)"
          />
          <img
            class="file-icon"
            :src="materialFileIconForNode({ name: item.name, path: item.path, isDir: false }).src"
            alt=""
          />
          <span class="file-name" :class="`git-${item.state}`">{{ item.name }}</span>
          <span class="file-directory">{{ item.directory }}</span>
          <span class="file-state" :class="`git-${item.state}`">{{ statusLabel(item) }}</span>
        </li>
      </ul>
    </Transition>
  </section>
</template>

<style scoped>
.change-group {
  border-bottom: 1px solid var(--color-border);
}

.group-header {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-4);
  min-height: 34px;
  padding: 0 var(--space-8);
}

.group-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
  cursor: pointer;
}

.group-toggle svg {
  flex: 0 0 auto;
  transition: transform 180ms ease;
}

.group-toggle svg.expanded {
  transform: rotate(90deg);
}

.group-count,
.file-directory {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  white-space: nowrap;
}

.change-list {
  margin: 0;
  padding: 0 0 var(--space-4);
  list-style: none;
}

.change-row {
  display: grid;
  grid-template-columns: 18px 16px minmax(72px, auto) minmax(0, 1fr) 16px;
  align-items: center;
  gap: var(--space-6);
  min-height: 30px;
  padding: 0 var(--space-8);
  padding-left: var(--space-24);
  transition: background 160ms ease;
}

.change-row:hover {
  background: var(--color-selection-blue-soft);
}

.file-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

.file-name,
.file-directory {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-name {
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.file-state {
  justify-self: end;
  font-family: var(--font-code);
  font-size: calc(11px * var(--font-scale));
}

.git-modified {
  color: var(--color-git-modified);
}

.git-added {
  color: var(--color-git-added);
}

.git-untracked {
  color: var(--color-git-untracked);
}

.git-conflicted {
  color: var(--color-danger);
}

.git-deleted {
  color: var(--color-git-deleted);
}

.git-renamed {
  color: var(--color-git-renamed);
}

.group-collapse-enter-active,
.group-collapse-leave-active {
  overflow: hidden;
  transition: opacity 160ms ease, transform 160ms ease;
}

.group-collapse-enter-from,
.group-collapse-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
