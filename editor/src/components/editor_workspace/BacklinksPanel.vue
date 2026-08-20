<!--
  Backlinks bottom panel for the active Markdown document.

  Usage:
  Displays incoming source files and the exact wiki-link spelling found in
  each source. Selecting a source opens that file in the workspace.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import type { BacklinkEntry, BacklinkOccurrence } from './backlinks'

defineProps<{
  entries: BacklinkEntry[]
  loading: boolean
}>()

const emit = defineEmits<{
  close: []
  open: [path: string]
}>()

function targetTypeLabel(occurrence: BacklinkOccurrence): string {
  if (occurrence.targetKind === 'heading') return `标题 · ${occurrence.targetLabel}`
  if (occurrence.targetKind === 'block') return `块 · ${occurrence.targetLabel}`
  return '文章'
}

function sourceTargetLabels(entry: BacklinkEntry): string[] {
  return [...new Set(entry.occurrences.map(targetTypeLabel))]
}
</script>

<template>
  <aside class="backlinks-panel" aria-label="反向链接">
    <header class="backlinks-header">
      <div class="backlinks-title">
        <IcIcon name="link" :size="15" />
        <strong>反向链接</strong>
        <span>{{ loading ? '读取中' : `${entries.length} 个文件` }}</span>
      </div>
      <button type="button" title="关闭反向链接" aria-label="关闭反向链接" @click="emit('close')">
        <IcIcon name="close" :size="14" />
      </button>
    </header>

    <div class="backlinks-content">
      <p v-if="loading" class="backlinks-empty">正在查找链接当前文件的 Markdown 文档…</p>
      <p v-else-if="entries.length === 0" class="backlinks-empty">没有文件链接到当前文章</p>
      <button
        v-for="entry in entries"
        v-else
        :key="entry.path"
        class="backlink-entry"
        type="button"
        @click="emit('open', entry.path)"
      >
        <span class="backlink-file-row">
          <span class="backlink-file-name">{{ entry.name }}</span>
          <span class="backlink-file-path">{{ entry.path }}</span>
          <span class="backlink-file-targets">
            <span v-for="label in sourceTargetLabels(entry)" :key="label" class="backlink-target-kind">{{ label }}</span>
          </span>
        </span>
        <span v-for="(occurrence, index) in entry.occurrences" :key="`${occurrence.raw}-${index}`" class="backlink-token-row">
          <code>{{ occurrence.raw }}</code>
          <span class="backlink-target-kind">{{ targetTypeLabel(occurrence) }}</span>
        </span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.backlinks-panel {
  display: flex;
  flex: 0 0 min(240px, 34vh);
  min-height: 132px;
  flex-direction: column;
  margin: 0 var(--space-10) var(--space-10);
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
}

.backlinks-header,
.backlinks-title,
.backlink-file-row,
.backlink-token-row {
  display: flex;
  align-items: center;
}

.backlinks-header {
  justify-content: space-between;
  min-height: 34px;
  padding: 0 var(--space-10);
  background: var(--color-canvas-soft);
}

.backlinks-title { gap: var(--space-6); }
.backlinks-title strong { font-size: calc(12px * var(--font-scale)); }
.backlinks-title span,
.backlink-file-path { color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }

.backlinks-header button {
  display: grid;
  width: 24px;
  height: 24px;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
}

.backlinks-header button:hover { background: var(--color-primary-softer); color: var(--color-primary); }
.backlinks-content { display: grid; gap: var(--space-6); padding: var(--space-8); overflow: auto; }
.backlinks-empty { margin: auto; padding: var(--space-16); color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }

.backlink-entry {
  display: grid;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-canvas-soft);
  color: var(--color-text);
  text-align: left;
}

.backlink-entry:hover { background: var(--color-primary-softer); }
.backlink-file-row { min-width: 0; gap: var(--space-8); }
.backlink-file-name { font-size: calc(12px * var(--font-scale)); font-weight: 600; }
.backlink-file-path { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.backlink-file-targets { display: flex; flex: 0 0 auto; gap: var(--space-4); margin-left: auto; }
.backlink-token-row { justify-content: space-between; gap: var(--space-10); }
.backlink-token-row code { min-width: 0; overflow: hidden; color: var(--color-text-secondary); font-family: var(--font-code); font-size: calc(11px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.backlink-target-kind { flex: 0 0 auto; padding: 2px var(--space-6); border-radius: 999px; background: var(--color-primary-soft); color: var(--color-primary); font-size: calc(10px * var(--font-scale)); }
</style>
