<!--
  Wiki-link file suggestion menu.

  Usage:
  CodeEditor positions this menu at the active [[ / ![[ caret and supplies
  filtered knowledge-file candidates from the shared wikiLinks helper.
-->
<script setup lang="ts">
import type { WikiLinkSuggestion } from './wikiLinks'

defineProps<{
  items: WikiLinkSuggestion[]
  activeIndex: number
  position: { left: string; top: string }
}>()

const emit = defineEmits<{
  select: [item: WikiLinkSuggestion]
  activate: [index: number]
}>()
</script>

<template>
  <div class="wiki-link-suggest ui-floating-menu-surface" :style="position" role="listbox" aria-label="Wiki 链接文件">
    <div v-if="items.length" class="wiki-link-suggest-list">
      <button
        v-for="(item, index) in items"
        :key="item.path"
        class="wiki-link-suggest-item"
        :class="{ active: index === activeIndex }"
        type="button"
        role="option"
        :aria-selected="index === activeIndex"
        @mouseenter="emit('activate', index)"
        @mousedown.prevent="emit('select', item)"
      >
        <strong>{{ item.title }}</strong>
        <span>{{ item.folder }}</span>
      </button>
    </div>
    <p v-else class="wiki-link-suggest-empty">没有匹配的文件</p>
    <footer>输入 # 链接标题　输入 ^ 链接文本块　输入 | 指定显示文本</footer>
  </div>
</template>

<style scoped>
.wiki-link-suggest {
  position: absolute;
  z-index: 60;
  width: min(420px, calc(100% - 24px));
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-window);
}

.wiki-link-suggest-list {
  max-height: 300px;
  overflow-y: auto;
  padding: var(--space-4);
}

.wiki-link-suggest-item {
  display: grid;
  width: 100%;
  gap: 1px;
  padding: var(--space-6) var(--space-10);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  text-align: left;
}

.wiki-link-suggest-item:hover,
.wiki-link-suggest-item.active {
  background: var(--color-primary-softer);
}

.wiki-link-suggest-item strong {
  overflow: hidden;
  font-family: var(--font-text);
  font-size: calc(14px * var(--font-scale));
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-link-suggest-item span,
.wiki-link-suggest-empty,
.wiki-link-suggest footer {
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.wiki-link-suggest-empty {
  margin: 0;
  padding: var(--space-16);
  text-align: center;
}

.wiki-link-suggest footer {
  padding: var(--space-8) var(--space-10);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
  white-space: nowrap;
}
</style>
