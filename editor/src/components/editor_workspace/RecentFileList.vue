<!--
  Recent file browsing list.

  Usage:
  Renders date-grouped recent file cards with path, last visit time, and
  index/graph status. File opening is delegated to the parent panel.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import RecentFileThumbnail from '@/components/editor_workspace/RecentFileThumbnail.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'
import type { RecentFileGroup } from '@/utils/recentFileHistory'
import { recentFileParentPath } from '@/utils/recentFileHistory'

defineProps<{
  groups: RecentFileGroup[]
  selectedPath: string
  hasHistory: boolean
}>()

const emit = defineEmits<{
  select: [node: KnowledgeFileNode]
  contextMenu: [node: KnowledgeFileNode, event: MouseEvent]
}>()

/** Formats the stored ISO timestamp for the compact card footer. */
function formatViewedAt(value: string): string {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** Maps vector-index state to its accessible icon presentation. */
function indexStatus(node: KnowledgeFileNode) {
  if (node.indexStatus === 'indexed' || node.indexStatus === 'clean') {
    return { icon: 'check-circle', className: 'is-ready', label: '已索引' }
  }
  if (node.indexStatus === 'ignored') {
    return { icon: 'block', className: 'is-muted', label: '已忽略' }
  }
  if (node.indexStatus === 'failed') {
    return { icon: 'error-outline', className: 'is-error', label: '索引失败' }
  }
  return { icon: 'error-outline', className: 'is-pending', label: '未索引' }
}

/** Maps graph-extraction state to its accessible icon presentation. */
function graphStatus(node: KnowledgeFileNode) {
  if (node.graphStatus === 'graphed') {
    return { icon: 'hub', className: 'is-ready', label: '已入图' }
  }
  if (node.graphStatus === 'ignored') {
    return { icon: 'block', className: 'is-muted', label: '已忽略' }
  }
  return { icon: 'git', className: 'is-pending', label: '未入图' }
}
</script>

<template>
  <div class="recent-file-list">
    <section v-for="group in groups" :key="group.key" class="recent-file-group">
      <h3 class="recent-file-group-title">{{ group.label }}</h3>
      <ul class="recent-file-items">
        <li v-for="item in group.items" :key="item.node.path">
          <button
            type="button"
            class="recent-file-card"
            :class="{ selected: item.node.path === selectedPath }"
            :aria-label="`打开 ${item.node.name}`"
            @click="emit('select', item.node)"
            @contextmenu.prevent="emit('contextMenu', item.node, $event)"
          >
            <RecentFileThumbnail :node="item.node" />
            <span class="recent-file-main">
              <span class="recent-file-name" :title="item.node.name">{{ item.node.name }}</span>
              <span class="recent-file-path" :title="recentFileParentPath(item.node.path)">
                {{ recentFileParentPath(item.node.path) }}
              </span>
            </span>
            <span class="recent-file-meta">
              <time :datetime="item.lastViewedAt">{{ formatViewedAt(item.lastViewedAt) }}</time>
              <span class="recent-file-statuses">
                <span
                  :class="['recent-file-status', indexStatus(item.node).className]"
                  :title="indexStatus(item.node).label"
                  :aria-label="indexStatus(item.node).label"
                >
                  <IcIcon :name="indexStatus(item.node).icon" :size="12" />
                </span>
                <span
                  :class="['recent-file-status', graphStatus(item.node).className]"
                  :title="graphStatus(item.node).label"
                  :aria-label="graphStatus(item.node).label"
                >
                  <IcIcon :name="graphStatus(item.node).icon" :size="12" />
                </span>
              </span>
            </span>
          </button>
        </li>
      </ul>
    </section>

    <p v-if="groups.length === 0" class="recent-file-empty">
      {{ hasHistory ? '没有匹配的最近浏览文件' : '还没有浏览记录' }}
    </p>
  </div>
</template>

<style scoped>
.recent-file-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0 var(--space-8) var(--space-12);
}

.recent-file-group + .recent-file-group {
  margin-top: var(--space-12);
}

.recent-file-group-title {
  margin: 0;
  padding: var(--space-8) var(--space-4) var(--space-6);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
}

.recent-file-items {
  display: grid;
  gap: var(--space-6);
  margin: 0;
  padding: 0;
  list-style: none;
}

.recent-file-card {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: var(--space-8);
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease;
}

.recent-file-card:hover {
  border-color: var(--color-border-strong);
  background: var(--color-bg-hover);
}

.recent-file-card.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.recent-file-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.recent-file-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
}

.recent-file-name,
.recent-file-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-file-name {
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
}

.recent-file-path {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.recent-file-meta {
  display: flex;
  grid-column: 1 / -1;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-6);
  color: var(--color-text-muted);
  font-size: calc(9px * var(--font-scale));
}

.recent-file-statuses,
.recent-file-status {
  display: inline-flex;
  align-items: center;
}

.recent-file-statuses {
  gap: var(--space-6);
}

.recent-file-status {
  white-space: nowrap;
}

.recent-file-status.is-ready {
  color: var(--color-success);
}

.recent-file-status.is-error {
  color: var(--color-danger);
}

.recent-file-status.is-pending {
  color: var(--color-warning);
}

.recent-file-status.is-muted {
  color: var(--color-text-muted);
}

.recent-file-empty {
  margin: var(--space-20) var(--space-8);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  text-align: center;
}
</style>
