<!--
  Visual ingestion and graph progress page.

  Usage:
  Shows active ingestion rows, active graph extraction row, and merged
  ingestion/graph history with source-type filtering.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { HistorySourceType, IngestionHistoryItem, IngestionQueueItem } from '@/types/knowledge'

type IngestionTab = 'queue' | 'graph-queue' | 'history'

const workspaceStore = useWorkspaceStore()
const activeTab = computed({
  get: () => workspaceStore.ingestionViewTab as IngestionTab,
  set: (val: IngestionTab) => { workspaceStore.ingestionViewTab = val },
})
const tabSwitchRef = ref<HTMLElement | null>(null)
const tabSliderStyle = ref({ width: '0px', left: '0px' })

function updateTabSlider() {
  nextTick(() => {
    const container = tabSwitchRef.value
    if (!container) return
    const active = container.querySelector('.tab-button.active') as HTMLElement | null
    if (!active) return
    tabSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

onMounted(updateTabSlider)
watch(activeTab, updateTabSlider)
const historyFilter = ref<HistorySourceType | 'all'>('all')

const queueRows = computed(() => workspaceStore.ingestionQueue)
const graphQueueRows = computed(() => workspaceStore.graphQueue)
type HistoryRow = IngestionHistoryItem & { sourceType: HistorySourceType; sourceSort: number }

const allHistoryRows = computed(() => {
  const items: HistoryRow[] = [
    ...workspaceStore.ingestionHistory.map((item, i) => ({
      ...item,
      sourceType: (item.sourceType ?? 'ingestion') as HistorySourceType,
      sourceSort: i,
    })),
    ...workspaceStore.graphHistory.map((item, i) => ({
      ...item,
      sourceType: 'graph' as HistorySourceType,
      sourceSort: i + 100000,
    })),
  ]
  items.sort((a, b) => new Date(b.finishedAt).getTime() - new Date(a.finishedAt).getTime())
  return items
})

const historyRows = computed(() => {
  if (historyFilter.value === 'all') return allHistoryRows.value
  return allHistoryRows.value.filter((row) => row.sourceType === historyFilter.value)
})

const queueColumns = 'minmax(220px, 2fr) 150px 150px 120px 132px'
const graphQueueColumns = 'minmax(220px, 2fr) 150px 150px 120px 120px 132px'
const historyColumns = 'minmax(220px, 2fr) 80px 140px 132px 160px 1fr'

async function refresh() {
  await workspaceStore.loadKnowledgeTree()
}

function startIngestion() {
  workspaceStore.ingestionViewTab = 'queue'
  workspaceStore.mainView = 'ingestion'
  workspaceStore.markIndexing()
}

function startGraphExtraction() {
  workspaceStore.ingestionViewTab = 'graph-queue'
  workspaceStore.mainView = 'ingestion'
  workspaceStore.startGraphRebuild()
}

function formatSize(size?: number): string {
  if (size === undefined || Number.isNaN(size)) return '-'
  if (size < 1024) return `${size} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = size / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`
}

function fileKind(row: IngestionQueueItem | (IngestionHistoryItem & { sourceType: HistorySourceType })): string {
  if (row.isDir) return '文件夹'
  const dotIndex = row.name.lastIndexOf('.')
  if (dotIndex < 0 || dotIndex === row.name.length - 1) return '文件'
  return row.name.slice(dotIndex + 1).toUpperCase()
}

function formatDate(value?: string): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function queueStatusLabel(status: IngestionQueueItem['status']): string {
  return status === 'running' ? '正在灌库' : '等待灌库'
}

function historyStatusLabel(status: IngestionHistoryItem['status']): string {
  if (status === 'finished') return '已完成'
  if (status === 'skipped') return '已跳过'
  return '失败'
}

function historySourceLabel(sourceType: HistorySourceType): string {
  return sourceType === 'graph' ? '图谱' : '灌库'
}

function historySummary(row: IngestionHistoryItem): string {
  if (row.message) return row.message
  const pieces = [
    row.filesIngested !== undefined ? `${row.filesIngested} 个入库` : '',
    row.filesSkipped !== undefined ? `${row.filesSkipped} 个跳过` : '',
    row.chunksCreated !== undefined ? `${row.chunksCreated} 个切片` : '',
  ].filter(Boolean)
  return pieces.join(' / ') || '-'
}
</script>

<template>
  <section class="ingestion-page">
    <header class="page-heading">
      <div ref="tabSwitchRef" class="tab-switch" role="tablist" aria-label="入库进度子页">
        <div class="tab-slider" :style="tabSliderStyle"></div>
        <button
          class="tab-button"
          :class="{ active: activeTab === 'queue' }"
          type="button"
          role="tab"
          @click="activeTab = 'queue'"
        >
          <IcIcon name="ingest" :size="17" />
          <span>入库队列</span>
        </button>
        <button
          class="tab-button"
          :class="{ active: activeTab === 'graph-queue' }"
          type="button"
          role="tab"
          @click="activeTab = 'graph-queue'"
        >
          <IcIcon name="hub" :size="17" />
          <span>图谱抽取队列</span>
        </button>
        <button
          class="tab-button"
          :class="{ active: activeTab === 'history' }"
          type="button"
          role="tab"
          @click="activeTab = 'history'"
        >
          <IcIcon name="history" :size="17" />
          <span>入库历史</span>
        </button>
      </div>
      <div class="heading-actions">
        <button
          v-if="activeTab === 'queue'"
          class="topbar-action-clone"
          :class="{ refreshing: workspaceStore.refreshing }"
          type="button"
          :disabled="workspaceStore.refreshing"
          title="重新灌库"
          aria-label="重新灌库"
          @click="startIngestion"
        >
          <IcIcon name="ingest" :size="14" />
        </button>
        <button
          v-else-if="activeTab === 'graph-queue'"
          class="topbar-action-clone"
          :class="{ refreshing: graphQueueRows.length > 0 }"
          type="button"
          :disabled="graphQueueRows.length > 0"
          title="图谱抽取"
          aria-label="图谱抽取"
          @click="startGraphExtraction"
        >
          <IcIcon name="hub" :size="14" />
        </button>
        <button class="refresh-btn" type="button" title="刷新" aria-label="刷新" @click="refresh">
          <IcIcon name="refresh" :size="16" class="refresh-svg" />
        </button>
        <button
          v-if="activeTab === 'history' && historyRows.length > 0"
          class="icon-button"
          type="button"
          title="清空历史"
          aria-label="清空历史"
          @click="workspaceStore.clearIngestionHistory(); workspaceStore.clearGraphHistory()"
        >
          <IcIcon name="trash" :size="16" />
        </button>
      </div>
    </header>

    <!-- Ingestion Queue Tab -->
    <div v-if="activeTab === 'queue'" class="file-table">
      <div class="file-table-head" :style="{ gridTemplateColumns: queueColumns }">
        <span>名称</span>
        <span>最后修改日期</span>
        <span>类型</span>
        <span>大小</span>
        <span>状态</span>
      </div>
      <TransitionGroup name="ingestion-row" tag="div" class="file-table-body">
        <div
          v-for="row in queueRows"
          :key="row.id"
          class="file-row"
          :class="row.status"
          :style="{ gridTemplateColumns: queueColumns }"
        >
          <span class="name-cell">
            <IcIcon v-if="row.isDir" name="folder" :size="16" class="kind-icon folder" />
            <IcIcon v-else name="document" :size="16" class="kind-icon file" />
            <span class="file-name" :title="row.path">{{ row.name }}</span>
          </span>
          <span>{{ row.mtime ?? '-' }}</span>
          <span>{{ fileKind(row) }}</span>
          <span>{{ formatSize(row.size) }}</span>
          <span class="status-cell">
            <IcIcon v-if="row.status === 'running'" name="spinner" :size="14" class="spin" />
            <IcIcon v-else name="radio-unchecked" :size="14" />
            <span class="status-pill" :class="row.status">{{ queueStatusLabel(row.status) }}</span>
          </span>
        </div>
      </TransitionGroup>
      <div v-if="queueRows.length === 0" class="empty-state">
        当前没有正在或等待灌库的文件
      </div>
    </div>

    <!-- Graph Queue Tab -->
    <div v-else-if="activeTab === 'graph-queue'" class="file-table">
      <div class="file-table-head" :style="{ gridTemplateColumns: graphQueueColumns }">
        <span>名称</span>
        <span>最后修改日期</span>
        <span>类型</span>
        <span>大小</span>
        <span>进度</span>
        <span>状态</span>
      </div>
      <TransitionGroup name="ingestion-row" tag="div" class="file-table-body">
        <div
          v-for="row in graphQueueRows"
          :key="row.id"
          class="file-row"
          :class="row.status"
          :style="{ gridTemplateColumns: graphQueueColumns }"
        >
          <span class="name-cell">
            <IcIcon name="document" :size="16" class="kind-icon file" />
            <span class="file-name" :title="row.path">{{ row.name }}</span>
          </span>
          <span>{{ row.mtime ?? '-' }}</span>
          <span>{{ fileKind(row) }}</span>
          <span>{{ formatSize(row.size) }}</span>
          <span class="progress-cell">
            <div v-if="row.status === 'running' && row.progress !== undefined" class="progress-bar-wrap">
              <div class="progress-bar-fill" :style="{ width: `${row.progress}%` }" />
              <span class="progress-pct">{{ row.progress }}%</span>
            </div>
            <span v-else class="progress-na">-</span>
          </span>
          <span class="status-cell">
            <IcIcon v-if="row.status === 'running'" name="spinner" :size="14" class="spin" />
            <IcIcon v-else name="radio-unchecked" :size="14" />
            <span class="status-pill" :class="row.status">{{ row.status === 'running' ? '正在抽取' : '等待抽取' }}</span>
          </span>
        </div>
      </TransitionGroup>
      <div v-if="graphQueueRows.length === 0" class="empty-state">
        当前没有正在或等待抽取的任务
      </div>
    </div>

    <!-- Merged History Tab -->
    <div v-else class="file-table">
      <div class="file-table-head" :style="{ gridTemplateColumns: historyColumns }">
        <span>名称</span>
        <span>来源</span>
        <span>类型</span>
        <span>结果</span>
        <span>完成时间</span>
        <span>摘要</span>
      </div>
      <div class="file-table-body">
        <div class="history-filter-bar">
          <button
            class="filter-chip"
            :class="{ active: historyFilter === 'all' }"
            type="button"
            @click="historyFilter = 'all'"
          >全部</button>
          <button
            class="filter-chip"
            :class="{ active: historyFilter === 'ingestion' }"
            type="button"
            @click="historyFilter = 'ingestion'"
          >灌库</button>
          <button
            class="filter-chip"
            :class="{ active: historyFilter === 'graph' }"
            type="button"
            @click="historyFilter = 'graph'"
          >图谱</button>
        </div>
        <div
          v-for="row in historyRows"
          :key="`${row.sourceType}-${row.id}`"
          class="file-row"
          :class="row.status"
          :style="{ gridTemplateColumns: historyColumns }"
        >
          <span class="name-cell">
            <IcIcon v-if="row.isDir" name="folder" :size="16" class="kind-icon folder" />
            <IcIcon v-else-if="row.sourceType !== 'graph'" name="document" :size="16" class="kind-icon file" />
            <IcIcon v-else name="psychology" :size="16" class="kind-icon graph" />
            <span class="file-name" :title="row.path || row.name">{{ row.name }}</span>
          </span>
          <span class="history-source-cell">
            <span class="source-chip" :class="row.sourceType">{{ historySourceLabel(row.sourceType) }}</span>
          </span>
          <span>{{ fileKind(row) }}</span>
          <span class="status-cell">
            <IcIcon v-if="row.status === 'finished'" name="check-circle" :size="14" />
            <IcIcon v-else-if="row.status === 'skipped'" name="radio-unchecked" :size="14" />
            <IcIcon v-else name="cancel" :size="14" />
            <span class="status-pill" :class="row.status">{{ historyStatusLabel(row.status) }}</span>
          </span>
          <span>{{ formatDate(row.finishedAt) }}</span>
          <span class="summary-cell" :title="historySummary(row)">{{ historySummary(row) }}</span>
        </div>
      </div>
      <div v-if="historyRows.length === 0" class="empty-state">
        还没有历史记录
      </div>
    </div>
  </section>
</template>

<style scoped>
.ingestion-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-12);
  min-width: 0;
  min-height: 0;
  padding: var(--space-16);
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-ui);
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
}

.heading-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
}

.tab-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.tab-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-softer);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.tab-button,
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  z-index: 1;
}

.tab-button {
  position: relative;
  z-index: 1;
  height: 26px;
  padding: 0 var(--space-10);
  gap: var(--space-6);
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  outline: none;
}

.tab-button:hover,
.icon-button:hover {
  color: var(--color-primary);
}

.tab-button.active {
  color: var(--color-primary);
}

.icon-button {
  width: 32px;
  height: 32px;
  border-color: var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 5px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  outline: none;
  transition: all 0.3s;
}

.refresh-btn:hover {
  transform: rotate(90deg);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.refresh-svg {
  transition: all 0.3s;
}

.refresh-btn:hover .refresh-svg {
  stroke: var(--color-primary);
}

.topbar-action-clone {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 32px;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-muted);
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.topbar-action-clone :deep(svg) {
  transition: transform 0.3s;
}

.topbar-action-clone:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.topbar-action-clone:hover:not(:disabled) :deep(svg) {
  transform: rotate(90deg);
}

.topbar-action-clone.refreshing :deep(svg) {
  animation: spin 900ms linear infinite;
}

.topbar-action-clone:disabled {
  cursor: wait;
  opacity: 0.62;
}

.file-table {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: none;
}

.file-table-head,
.file-row {
  display: grid;
  align-items: center;
  min-width: 760px;
}

.file-table-head {
  position: sticky;
  top: 0;
  z-index: 2;
  min-height: 34px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.file-table-head span,
.file-row > span {
  min-width: 0;
  padding: 0 var(--space-12);
}

.file-row {
  min-height: 38px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.file-row:last-child {
  border-bottom: 0;
}

.file-row.running {
  background: linear-gradient(90deg, var(--color-primary-softer), transparent 72%);
}

.name-cell,
.status-cell,
.history-source-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-name,
.summary-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kind-icon.folder {
  color: var(--color-primary);
}

.kind-icon.file {
  color: var(--color-text-muted);
}

.kind-icon.graph {
  color: var(--color-primary);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.status-pill.running,
.status-pill.finished {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.status-pill.failed {
  border-color: rgba(220, 38, 38, 0.35);
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.history-filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-12);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.filter-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.filter-chip.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.source-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
}

.source-chip.ingestion {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-muted);
}

.source-chip.graph {
  border: 1px solid var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 180px;
  color: var(--color-text-muted);
  font-size: calc(13px * var(--font-scale));
}

.spin {
  animation: spin 900ms linear infinite;
}

.progress-cell {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.progress-bar-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: 18px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  overflow: hidden;
}

.progress-bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 3px;
  background: var(--color-primary);
  transition: width 300ms ease;
}

.progress-pct {
  position: relative;
  z-index: 1;
  margin: 0 auto;
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
  color: var(--color-text);
  line-height: 18px;
}

.progress-na {
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.ingestion-row-enter-active,
.ingestion-row-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.ingestion-row-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.ingestion-row-leave-to {
  opacity: 0;
  transform: translateX(18px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .ingestion-page {
    padding: var(--space-12);
  }

  .page-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .heading-actions {
    justify-content: space-between;
  }
}
</style>
