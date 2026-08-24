<!--
  Markdown heading outline sidebar.

  Usage:
  Pass the parsed heading tree and active heading id. The component owns tree
  expansion and title search, and emits a heading when the user navigates.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import MarkdownOutlineNode from './MarkdownOutlineNode.vue'
import {
  expandableHeadingIds,
  filterMarkdownOutline,
  headingAncestorIds,
  type MarkdownOutlineItem,
} from './markdownOutline'

const props = defineProps<{
  items: MarkdownOutlineItem[]
  activeId: string
  open: boolean
}>()

const emit = defineEmits<{
  navigate: [item: MarkdownOutlineItem]
}>()

const query = ref('')
const expandedKeys = ref<string[]>([])
const visibleItems = computed(() => filterMarkdownOutline(props.items, query.value))

/** Expands every heading that owns child headings. */
function expandAll() {
  expandedKeys.value = expandableHeadingIds(visibleItems.value)
}

/** Collapses the tree to its root heading rows. */
function collapseAll() {
  expandedKeys.value = []
}

/** Toggles one checkbox branch while keeping expansion state parent-owned. */
function toggleHeading(id: string) {
  expandedKeys.value = expandedKeys.value.includes(id)
    ? expandedKeys.value.filter((key) => key !== id)
    : [...expandedKeys.value, id]
}

watch(() => props.items, expandAll, { immediate: true })
watch(query, () => {
  if (query.value.trim()) expandAll()
})
watch(() => props.activeId, (id) => {
  if (!id || query.value.trim()) return
  expandedKeys.value = [...new Set([...expandedKeys.value, ...headingAncestorIds(props.items, id)])]
})
</script>

<template>
  <aside class="markdown-outline" :class="{ open }" :aria-hidden="!open" :inert="!open">
    <header class="outline-toolbar">
      <div class="outline-actions">
        <button class="outline-header-action expand-action" type="button" title="全部展开" aria-label="全部展开" @click="expandAll">
          <IcIcon name="unfold" :size="14" />
          <span>全部展开</span>
        </button>
        <button class="outline-header-action collapse-action" type="button" title="全部折叠" aria-label="全部折叠" @click="collapseAll">
          <IcIcon name="unfold-less" :size="14" />
          <span>全部折叠</span>
        </button>
      </div>
      <label class="outline-search">
        <IcIcon name="search" :size="15" />
        <input v-model="query" type="search" placeholder="搜索标题" aria-label="搜索标题" />
        <button v-if="query" class="outline-search-clear" type="button" title="清除搜索" aria-label="清除搜索" @click="query = ''">
          <IcIcon name="close" :size="12" />
        </button>
      </label>
    </header>

    <div class="outline-scroll">
      <div v-if="visibleItems.length" class="tree-container">
        <ul class="outline-tree-list">
          <MarkdownOutlineNode
            v-for="item in visibleItems"
            :key="item.id"
            :item="item"
            :expanded-ids="expandedKeys"
            :active-id="activeId"
            :query="query"
            @toggle="toggleHeading"
            @navigate="emit('navigate', $event)"
          />
        </ul>
      </div>
      <p v-else class="outline-empty">{{ query ? '没有匹配的标题' : '当前文档没有标题' }}</p>
    </div>
  </aside>
</template>

<style scoped>
.markdown-outline {
  position: absolute;
  inset: 0 0 0 auto;
  z-index: 8;
  display: flex;
  width: min(308px, 76%);
  min-width: 240px;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  opacity: 0;
  pointer-events: none;
  transform: translateX(100%);
  transition:
    opacity 220ms cubic-bezier(0.23, 1, 0.32, 1),
    transform 260ms cubic-bezier(0.32, 0.72, 0, 1);
}

.markdown-outline.open {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}

.outline-toolbar {
  display: grid;
  gap: var(--space-8);
  padding: var(--space-10) var(--space-12) var(--space-8);
}

.outline-actions {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.outline-header-action {
  display: inline-flex;
  width: auto;
  height: 28px;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  padding: 0 var(--space-6);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(11px * var(--font-scale));
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), transform 140ms cubic-bezier(0.23, 1, 0.32, 1);
}

.outline-header-action:active {
  transform: scale(0.92);
}

.outline-header-action :deep(svg) {
  transition: transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}

.outline-search {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: var(--space-6);
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  transition: border-color var(--transition-fast);
}

.outline-search:focus-within {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.outline-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
}

.outline-search input::-webkit-search-cancel-button {
  display: none;
}

.outline-search-clear {
  display: inline-flex;
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), transform 140ms cubic-bezier(0.23, 1, 0.32, 1);
}

.outline-search-clear:active {
  transform: scale(0.88);
}

.outline-scroll {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: var(--space-8) 0;
}

.tree-container {
  box-sizing: border-box;
  width: calc(100% - 20px);
  margin: 0 10px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-canvas);
  box-shadow: 0 1px 2px color-mix(in srgb, var(--color-text) 5%, transparent);
}

.outline-tree-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.outline-empty {
  margin: var(--space-16);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  text-align: center;
}

@media (hover: hover) and (pointer: fine) {
  .outline-header-action:hover,
  .outline-search-clear:hover {
    background: var(--color-selection-blue-soft);
    color: var(--color-selection-blue);
  }

  .expand-action:hover :deep(svg) {
    transform: scaleY(1.18);
  }

  .collapse-action:hover :deep(svg) {
    transform: scaleY(0.82);
  }
}

@media (prefers-reduced-motion: reduce) {
  .markdown-outline {
    transform: none;
    transition: opacity 160ms ease;
  }

  .outline-header-action,
  .outline-header-action :deep(svg),
  .outline-search-clear {
    transition: none;
  }
}
</style>
