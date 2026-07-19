<!--
  Visual ingestion progress page.

  Usage:
  Shows active ingestion rows and persisted ingestion history in Explorer-like
  list views.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  CheckCircle2,
  CircleDashed,
  FileText,
  Folder,
  History,
  Loader2,
  RefreshCw,
  Trash2,
  XCircle,
} from 'lucide-vue-next'

import { useWorkspaceStore } from '@/stores/workspace'
import type { IngestionHistoryItem, IngestionQueueItem } from '@/types/knowledge'

type IngestionTab = 'queue' | 'history'

const workspaceStore = useWorkspaceStore()
const activeTab = ref<IngestionTab>('queue')

const queueRows = computed(() => workspaceStore.ingestionQueue)
const historyRows = computed(() => workspaceStore.ingestionHistory)
const queueColumns = 'minmax(220px, 2fr) 150px 150px 120px 132px'
const historyColumns = 'minmax(220px, 2fr) 140px 132px 160px 1fr'

async function refresh() {
  await workspaceStore.loadKnowledgeTree()
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

function fileKind(row: IngestionQueueItem | IngestionHistoryItem): string {
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
      <div>
        <h1>入库进度</h1>
        <p>{{ activeTab === 'queue' ? `${queueRows.length} 个文件正在或等待灌库` : `${historyRows.length} 条历史记录` }}</p>
      </div>
      <div class="heading-actions">
        <div class="tab-switch" role="tablist" aria-label="入库进度子页">
          <button
            class="tab-button"
            :class="{ active: activeTab === 'queue' }"
            type="button"
            role="tab"
            @click="activeTab = 'queue'"
          >
            <CircleDashed :size="15" />
            <span>入库队列</span>
          </button>
          <button
            class="tab-button"
            :class="{ active: activeTab === 'history' }"
            type="button"
            role="tab"
            @click="activeTab = 'history'"
          >
            <History :size="15" />
            <span>入库历史</span>
          </button>
        </div>
        <button class="icon-button" type="button" title="刷新" aria-label="刷新" @click="refresh">
          <RefreshCw :size="16" />
        </button>
        <button
          v-if="activeTab === 'history' && historyRows.length > 0"
          class="icon-button"
          type="button"
          title="清空历史"
          aria-label="清空历史"
          @click="workspaceStore.clearIngestionHistory()"
        >
          <Trash2 :size="16" />
        </button>
      </div>
    </header>

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
            <Folder v-if="row.isDir" :size="16" class="kind-icon folder" />
            <FileText v-else :size="16" class="kind-icon file" />
            <span class="file-name" :title="row.path">{{ row.name }}</span>
          </span>
          <span>{{ row.mtime ?? '-' }}</span>
          <span>{{ fileKind(row) }}</span>
          <span>{{ formatSize(row.size) }}</span>
          <span class="status-cell">
            <Loader2 v-if="row.status === 'running'" :size="14" class="spin" />
            <CircleDashed v-else :size="14" />
            <span class="status-pill" :class="row.status">{{ queueStatusLabel(row.status) }}</span>
          </span>
        </div>
      </TransitionGroup>
      <div v-if="queueRows.length === 0" class="empty-state">
        当前没有正在或等待灌库的文件
      </div>
    </div>

    <div v-else class="file-table">
      <div class="file-table-head" :style="{ gridTemplateColumns: historyColumns }">
        <span>名称</span>
        <span>类型</span>
        <span>结果</span>
        <span>完成时间</span>
        <span>摘要</span>
      </div>
      <div class="file-table-body">
        <div
          v-for="row in historyRows"
          :key="row.id"
          class="file-row"
          :class="row.status"
          :style="{ gridTemplateColumns: historyColumns }"
        >
          <span class="name-cell">
            <Folder v-if="row.isDir" :size="16" class="kind-icon folder" />
            <FileText v-else :size="16" class="kind-icon file" />
            <span class="file-name" :title="row.path">{{ row.name }}</span>
          </span>
          <span>{{ fileKind(row) }}</span>
          <span class="status-cell">
            <CheckCircle2 v-if="row.status === 'finished'" :size="14" />
            <CircleDashed v-else-if="row.status === 'skipped'" :size="14" />
            <XCircle v-else :size="14" />
            <span class="status-pill" :class="row.status">{{ historyStatusLabel(row.status) }}</span>
          </span>
          <span>{{ formatDate(row.finishedAt) }}</span>
          <span class="summary-cell" :title="historySummary(row)">{{ historySummary(row) }}</span>
        </div>
      </div>
      <div v-if="historyRows.length === 0" class="empty-state">
        还没有入库历史
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

.page-heading h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.page-heading p {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.heading-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
}

.tab-switch {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
}

.tab-button,
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-text-muted);
}

.tab-button {
  gap: 6px;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
}

.tab-button:hover,
.tab-button.active,
.icon-button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.tab-button.active {
  background: var(--color-primary-soft);
}

.icon-button {
  width: 32px;
  height: 32px;
  border-color: var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.file-table {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
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
  font-size: 12px;
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
  font-size: 12px;
}

.file-row:last-child {
  border-bottom: 0;
}

.file-row.running {
  background: linear-gradient(90deg, var(--color-primary-softer), transparent 72%);
}

.name-cell,
.status-cell {
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

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: 11px;
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

.empty-state {
  display: grid;
  place-items: center;
  min-height: 180px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.spin {
  animation: spin 900ms linear infinite;
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
