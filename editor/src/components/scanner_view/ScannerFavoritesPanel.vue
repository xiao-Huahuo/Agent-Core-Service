<!--
  Scanner-only favorites page content.

  Reuses ScannerHistoryList and opens a selected favorite in the main scanner
  result page without duplicating history-card behavior.
-->
<script setup lang="ts">
import { onMounted } from 'vue'

import ScannerHistoryList from '@/components/scanner_view/ScannerHistoryList.vue'
import { useScannerStore } from '@/stores/scanner'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ScannerRecord } from '@/api/scanner'

const scannerStore = useScannerStore()
const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

/** Open a favorite scanner record in the full scanner workspace. */
async function open(record: ScannerRecord): Promise<void> {
  scannerStore.activeId = record.scan_id
  await scannerStore.refreshActive()
  workspaceStore.setMainView('scanner')
}

/** Reveal the managed original for a favorite scanner record. */
async function reveal(record: ScannerRecord): Promise<void> {
  const separator = window.agentEditorDesktop?.platform === 'win32' ? '\\' : '/'
  const root = settingsStore.profile.knowledgeDir.replace(/[\\/]+$/u, '')
  await window.agentEditorDesktop?.showItemInFolder?.(`${root}${separator}${record.source_path.replace(/\//gu, separator)}`)
}

/** Confirm deletion from both scanner history and favorites. */
async function remove(record: ScannerRecord): Promise<void> {
  if (!window.confirm(`删除“${record.source_name}”的扫描历史和受管文件？此操作无法撤销。`)) return
  await scannerStore.remove(record.scan_id)
}

onMounted(() => { void scannerStore.load() })
</script>

<template>
  <section class="scanner-favorites-panel">
    <ScannerHistoryList :records="scannerStore.records" favorites-only @select="open" @reveal="reveal" @remove="remove" />
  </section>
</template>

<style scoped>
.scanner-favorites-panel { width: min(920px,100%); height: 100%; min-height: 0; margin: 0 auto; padding: 12px; overflow: hidden; }
.scanner-favorites-panel :deep(.scanner-history-list) { grid-template-columns: repeat(auto-fill,minmax(230px,1fr)); }
@media (max-width: 480px) { .scanner-favorites-panel { padding: 8px; } .scanner-favorites-panel :deep(.scanner-history-list) { grid-template-columns: minmax(0,1fr); } }
</style>
