<!--
  Recursive Markdown outline node using the user-supplied checkbox tree.

  Usage:
  Render one parsed heading, forward branch toggles to the parent expansion
  state, and emit navigation for both branch labels and leaf rows.
-->
<script setup lang="ts">
import { computed } from 'vue'

import type { MarkdownOutlineItem } from './markdownOutline'

defineOptions({ name: 'MarkdownOutlineNode' })

const props = defineProps<{
  item: MarkdownOutlineItem
  expandedIds: string[]
  activeId: string
  query: string
}>()

const emit = defineEmits<{
  toggle: [id: string]
  navigate: [item: MarkdownOutlineItem]
}>()

/** Stable checkbox id used by the native label-driven collapse behavior. */
const toggleId = computed(() => `outline-${props.item.id}-toggle`)
/** Whether the parent-controlled expansion list currently opens this branch. */
const expanded = computed(() => props.expandedIds.includes(props.item.id))

/** Navigates to the heading and explicitly toggles the branch for every click target, including SVG icons. */
function activateBranch() {
  emit('navigate', props.item)
  emit('toggle', props.item.id)
}

/** Splits the heading into normal and bold search-match fragments. */
function titleParts(text: string) {
  const needle = props.query.trim()
  if (!needle) return [{ text, match: false }]
  const lowerText = text.toLocaleLowerCase()
  const lowerNeedle = needle.toLocaleLowerCase()
  const parts: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  while (cursor < text.length) {
    const index = lowerText.indexOf(lowerNeedle, cursor)
    if (index < 0) {
      parts.push({ text: text.slice(cursor), match: false })
      break
    }
    if (index > cursor) parts.push({ text: text.slice(cursor, index), match: false })
    parts.push({ text: text.slice(index, index + needle.length), match: true })
    cursor = index + needle.length
  }
  return parts
}
</script>

<template>
  <li class="tree-item">
    <template v-if="item.children.length">
      <input
        :id="toggleId"
        type="checkbox"
        class="tree-toggle"
        :checked="expanded"
      />
      <label
        :for="toggleId"
        class="tree-label"
        :class="{ 'is-selected': item.id === activeId }"
        role="button"
        tabindex="0"
        @click.prevent="activateBranch"
        @keydown.enter.prevent="activateBranch"
        @keydown.space.prevent="activateBranch"
      >
        <svg class="icon folder-closed-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 2H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
        </svg>
        <svg class="icon folder-open-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 2H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
          <path d="M2 10h20" />
        </svg>
        <span class="tree-name">
          <template v-for="(part, index) in titleParts(item.text)" :key="`${item.id}-${index}`">
            <strong v-if="part.match">{{ part.text }}</strong>
            <template v-else>{{ part.text }}</template>
          </template>
        </span>
      </label>

      <div class="tree-children-wrapper" :class="{ expanded }">
        <ul class="tree-children">
          <MarkdownOutlineNode
            v-for="child in item.children"
            :key="child.id"
            :item="child"
            :expanded-ids="expandedIds"
            :active-id="activeId"
            :query="query"
            @toggle="emit('toggle', $event)"
            @navigate="emit('navigate', $event)"
          />
        </ul>
      </div>
    </template>

    <div
      v-else
      class="file-item"
      :class="{ 'is-selected': item.id === activeId }"
      role="button"
      tabindex="0"
      @click="emit('navigate', item)"
      @keydown.enter.prevent="emit('navigate', item)"
    >
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
      <span class="tree-name">
        <template v-for="(part, index) in titleParts(item.text)" :key="`${item.id}-${index}`">
          <strong v-if="part.match">{{ part.text }}</strong>
          <template v-else>{{ part.text }}</template>
        </template>
      </span>
    </div>
  </li>
</template>

<style scoped>
.tree-children {
  min-height: 0;
  margin: 0 0 0 11px;
  padding: 0 0 0 11px;
  overflow: hidden;
  border-left: 1px solid var(--color-border);
  list-style: none;
}

.tree-item {
  position: relative;
  margin-top: 4px;
  list-style: none;
}

.tree-children > .tree-item::before {
  position: absolute;
  top: 14px;
  left: -11px;
  width: 11px;
  height: 1px;
  content: '';
  background-color: var(--color-border);
}

.tree-label,
.file-item {
  display: flex;
  box-sizing: border-box;
  width: 100%;
  height: 28px;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(14px * var(--font-scale));
  text-decoration: none;
  cursor: pointer;
  user-select: none;
  transition: background-color 200ms ease, color 200ms ease;
}

.tree-label:hover,
.file-item:hover {
  background-color: var(--color-surface-active);
}

.is-selected {
  background-color: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 500;
}

.icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.folder-open-icon {
  display: none;
}

.folder-closed-icon {
  display: block;
}

.tree-toggle:checked ~ .tree-label .folder-open-icon {
  display: block;
  color: var(--color-text);
}

.tree-toggle:checked ~ .tree-label .folder-closed-icon {
  display: none;
}

.tree-toggle {
  display: none;
}

.tree-children-wrapper {
  display: grid;
  grid-template-rows: minmax(0, 0fr);
  overflow: hidden;
  transition: grid-template-rows 300ms ease-in-out;
}

.tree-toggle:checked ~ .tree-children-wrapper,
.tree-children-wrapper.expanded {
  grid-template-rows: minmax(0, 1fr);
}

.tree-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-name strong {
  font-weight: var(--font-weight-semibold);
}

.file-item:focus-visible,
.tree-label:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

@media (prefers-reduced-motion: reduce) {
  .tree-children-wrapper {
    transition: none;
  }
}
</style>
