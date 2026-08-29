<!--
  File-resource-manager medium icon tile for split search results.

  Usage:
  SearchPage supplies the original KnowledgeFileNode returned by unified search.
  Single click previews and double click opens through the workspace pipeline.
-->
<script setup lang="ts">
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'SearchFileMediumTile' })

defineProps<{
  /** Original file-tree node from the backend result. */
  node: KnowledgeFileNode
  /** Whether the shared editor sidebar currently previews this file. */
  selected: boolean
}>()

const emit = defineEmits<{
  /** Request in-page readonly preview. */
  preview: [node: KnowledgeFileNode]
  /** Enter the regular editor workflow. */
  open: [node: KnowledgeFileNode]
}>()

/** Format a compact byte count matching the resource manager tile. */
function formatSize(size?: number): string {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <button
    class="search-file-medium-tile"
    :class="{ selected }"
    type="button"
    @click="emit('preview', node)"
    @dblclick="emit('open', node)"
  >
    <span class="tile-art">
      <img
        class="material-file-icon-medium"
        :src="materialFileIconForNode(node).src"
        alt=""
        aria-hidden="true"
      />
    </span>
    <span class="tile-name" :title="node.name">{{ node.name }}</span>
    <small>{{ formatSize(node.size) }}</small>
  </button>
</template>

<style scoped>
.search-file-medium-tile {
  position: relative;
  display: grid;
  width: 100%;
  min-width: 0;
  aspect-ratio: 1 / 1;
  grid-template-rows: 64px minmax(2.5em, auto) 14px;
  align-content: center;
  justify-items: center;
  gap: var(--space-4);
  padding: var(--space-8);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.07);
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  text-align: center;
  backdrop-filter: blur(14px) saturate(140%);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.search-file-medium-tile:hover {
  border-color: color-mix(in srgb, var(--color-primary) 32%, transparent);
  background: var(--color-selection-blue-soft);
}

.search-file-medium-tile.selected {
  border-color: var(--color-primary);
  background: var(--color-selection-blue-soft);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-primary) 36%, transparent);
}

.search-file-medium-tile:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.tile-art {
  display: grid;
  width: 100%;
  height: 64px;
  min-height: 64px;
  place-items: center;
}

.material-file-icon-medium {
  display: block;
  width: 52px;
  height: 52px;
  object-fit: contain;
  pointer-events: none;
}

.tile-name {
  display: -webkit-box;
  width: 100%;
  min-height: 2.5em;
  overflow: hidden;
  color: var(--color-text);
  line-height: 1.25;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

small {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}
</style>
