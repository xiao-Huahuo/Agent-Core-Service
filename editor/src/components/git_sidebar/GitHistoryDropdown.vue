<!--
  Anchored Git commit-history dropdown.

  Usage:
  Mount inside the sticky commit panel. Selecting an entry fills the shared
  commit summary and closes the dropdown without creating a modal layer.
-->
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

import { useGitStore } from '@/stores/git'

defineOptions({ name: 'GitHistoryDropdown' })

const gitStore = useGitStore()

/** Close the anchored list when the user presses Escape. */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') gitStore.historyOpen = false
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div class="history-dropdown" role="listbox" aria-label="历史提交记录">
    <button
      v-for="commit in gitStore.history.history"
      :key="commit.hash"
      type="button"
      role="option"
      @click="gitStore.useHistoryMessage(commit.summary)"
    >
      <span class="commit-summary">{{ commit.summary }}</span>
      <span class="commit-meta">
        {{ commit.short_hash }} · {{ commit.author }} · {{ new Date(commit.date).toLocaleString() }}
      </span>
    </button>
    <p v-if="gitStore.history.history.length === 0">暂无提交记录</p>
  </div>
</template>

<style scoped>
.history-dropdown {
  position: absolute;
  right: 0;
  bottom: calc(100% + var(--space-4));
  left: 0;
  z-index: 8;
  max-height: min(320px, 48vh);
  padding: var(--space-4);
  overflow: auto;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.history-dropdown button {
  display: grid;
  gap: var(--space-4);
  width: 100%;
  padding: var(--space-8);
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 160ms ease;
}

.history-dropdown button:hover,
.history-dropdown button:focus-visible {
  outline: 0;
  background: var(--color-primary-soft);
}

.commit-summary {
  overflow: hidden;
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.commit-meta,
.history-dropdown p {
  margin: 0;
  color: var(--color-text-muted);
  font-family: var(--font-code);
  font-size: calc(9px * var(--font-scale));
}

.history-dropdown p {
  padding: var(--space-16);
  text-align: center;
}
</style>
