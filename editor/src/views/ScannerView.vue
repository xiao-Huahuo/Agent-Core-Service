<!--
  Scanner page.

  Composes the persistent recent-history rail, upload/examples surface,
  progress state, and reusable split result editor.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import ScannerHistoryList from '@/components/scanner_view/ScannerHistoryList.vue'
import ScannerResultPanel from '@/components/scanner_view/ScannerResultPanel.vue'
import ScannerUploadPanel from '@/components/scanner_view/ScannerUploadPanel.vue'
import { useScannerStore } from '@/stores/scanner'
import { useSettingsStore } from '@/stores/settings'
import type { ScannerRecord } from '@/api/scanner'

defineOptions({ name: 'ScannerView' })

const scannerStore = useScannerStore()
const settingsStore = useSettingsStore()
const ocrEnabled = ref(true)
const submitting = ref(false)
const railPicker = ref<HTMLInputElement | null>(null)
let pollTimer: number | null = null

const running = computed(() => {
  const active = scannerStore.active
  return active && (active.status === 'queued' || active.status === 'running') ? active : null
})
const finished = computed(() => scannerStore.active?.status === 'finished' ? scannerStore.active : null)
const failed = computed(() => scannerStore.active?.status === 'failed' ? scannerStore.active : null)

/** Resolve the absolute managed source path for native reveal actions. */
function absoluteSourcePath(record: ScannerRecord): string {
  const separator = window.agentEditorDesktop?.platform === 'win32' ? '\\' : '/'
  const root = settingsStore.profile.knowledgeDir.replace(/[\\/]+$/u, '')
  return `${root}${separator}${record.source_path.replace(/\//gu, separator)}`
}

/** Select any terminal or running record and refresh its latest detail. */
async function selectRecord(record: ScannerRecord): Promise<void> {
  scannerStore.activeId = record.scan_id
  await scannerStore.refreshActive()
}

/** Submit one file/example through the shared real backend task flow. */
async function upload(file: File, sourceKind = 'file'): Promise<void> {
  submitting.value = true
  scannerStore.actionError = ''
  try {
    await scannerStore.upload(file, ocrEnabled.value, sourceKind)
  } catch (error) {
    scannerStore.actionError = error instanceof Error ? error.message : '上传失败'
  } finally {
    submitting.value = false
  }
}

/** Open the system picker from the left-rail upload action. */
function openRailPicker(): void {
  scannerStore.activeId = ''
  railPicker.value?.click()
}

/** Forward a file selected from the left rail into the shared upload flow. */
function onRailPick(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void upload(file)
  input.value = ''
}

/** Submit one webpage URL through the scanner crawler. */
async function crawl(url: string): Promise<void> {
  submitting.value = true
  scannerStore.actionError = ''
  try {
    await scannerStore.crawl(url, ocrEnabled.value)
  } catch (error) {
    scannerStore.actionError = error instanceof Error ? error.message : '网页解析失败'
  } finally {
    submitting.value = false
  }
}

/** Reveal the managed source copy in the operating-system file manager. */
async function reveal(record: ScannerRecord): Promise<void> {
  if (record.source_path) await window.agentEditorDesktop?.showItemInFolder?.(absoluteSourcePath(record))
}

/** Confirm and permanently delete one history record plus managed artifacts. */
async function remove(record: ScannerRecord): Promise<void> {
  if (!window.confirm(`删除“${record.source_name}”的扫描历史和受管文件？此操作无法撤销。`)) return
  try {
    await scannerStore.remove(record.scan_id)
  } catch (error) {
    scannerStore.actionError = error instanceof Error ? error.message : '删除失败'
  }
}

/** Poll only while at least one scanner task remains active. */
async function poll(): Promise<void> {
  if (!scannerStore.hasRunning) return
  await scannerStore.load()
  if (scannerStore.activeId) await scannerStore.refreshActive()
}

onMounted(async () => {
  await scannerStore.load()
  pollTimer = window.setInterval(() => { void poll().catch(() => undefined) }, 500)
})
onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
})
</script>

<template>
  <section class="scanner-view">
    <aside class="scanner-history-rail">
      <button class="scanner-new-button" type="button" :disabled="submitting" @click="openRailPicker">
        <IcIcon name="plus" :size="16" /><span>上传解析</span>
      </button>
      <input ref="railPicker" hidden type="file" @change="onRailPick" />
      <h2>最近解析</h2>
      <ScannerHistoryList
        :records="scannerStore.records"
        :active-id="scannerStore.activeId"
        @select="selectRecord"
        @reveal="reveal"
        @remove="remove"
      />
    </aside>

    <main class="scanner-main">
      <ScannerResultPanel v-if="finished" :key="finished.scan_id" :record="finished" @back="scannerStore.activeId = ''" @updated="scannerStore.upsert" />
      <section v-else-if="failed" class="scanner-failed">
        <IcIcon name="error-outline" :size="34" />
        <strong>解析失败</strong>
        <p>{{ failed.error }}</p>
        <button type="button" @click="scannerStore.activeId = ''">返回上传</button>
      </section>
      <ScannerUploadPanel v-else v-model:ocr-enabled="ocrEnabled" :running="running" @upload="upload" @crawl="crawl" />
      <p v-if="scannerStore.actionError" class="scanner-error">{{ scannerStore.actionError }}</p>
    </main>
  </section>
</template>

<style scoped>
.scanner-view { display: grid; grid-template-columns: 264px minmax(0,1fr); width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: hidden; background: var(--color-bg-app); color: var(--color-text); font-family: var(--font-ui); }
.scanner-history-rail { display: grid; grid-template-rows: auto auto minmax(0,1fr); min-width: 0; min-height: 0; padding: 12px 6px 0; border-right: 1px solid var(--color-border); background: var(--color-chrome-rail-bg); }
.scanner-new-button { display: flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; margin: 0 6px 10px; border: 1px solid var(--color-primary); border-radius: 9px; background: var(--color-primary-softer); color: var(--color-primary); font: inherit; font-size: calc(12px * var(--font-scale)); transition: background 150ms ease, transform 120ms ease; }
.scanner-new-button:hover { background: var(--color-primary-soft); }
.scanner-new-button:active { transform: scale(.98); }
.scanner-history-rail > h2 { margin: 2px 12px 8px; color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); font-weight: 650; }
.scanner-main { position: relative; min-width: 0; min-height: 0; overflow: hidden; }
.scanner-error { position: absolute; right: 18px; bottom: 18px; z-index: 10; max-width: min(520px,calc(100% - 36px)); margin: 0; padding: 9px 12px; border: 1px solid color-mix(in srgb,var(--color-danger) 45%,var(--color-border)); border-radius: 8px; background: var(--color-surface); color: var(--color-danger); font-size: calc(11px * var(--font-scale)); }
.scanner-failed { display: grid; place-items: center; align-content: center; min-height: 100%; padding: 24px; text-align: center; }
.scanner-failed :deep(svg) { color: var(--color-danger); }
.scanner-failed strong { margin-top: 12px; }
.scanner-failed p { max-width: 560px; color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
.scanner-failed button { min-height: 34px; padding: 0 14px; border: 0; border-radius: 8px; background: var(--color-primary); color: white; }
@media (max-width: 768px) { .scanner-view { grid-template-columns: minmax(0,1fr); grid-template-rows: 188px minmax(0,1fr); } .scanner-history-rail { border-right: 0; border-bottom: 1px solid var(--color-border); } .scanner-history-rail :deep(.scanner-history-list) { grid-auto-columns: minmax(220px,70%); grid-auto-flow: column; overflow-x: auto; overflow-y: hidden; } }
@media (max-width: 480px) { .scanner-view { grid-template-rows: 174px minmax(0,1fr); } }
@media (prefers-reduced-motion: reduce) { .scanner-new-button { transition: none; } }
</style>
