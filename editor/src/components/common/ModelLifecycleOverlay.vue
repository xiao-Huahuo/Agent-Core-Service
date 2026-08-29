<!--
  Independent model lifecycle floating notices.

  Usage:
  Mount once in App after the backend is reachable. Each managed model owns its
  own notice, real download progress, and explicit confirmation action.
-->
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import {
  downloadManagedModel,
  fetchModelManagement,
  type ManagedModelStatus,
} from '@/api/settings'
import PixelLoader from '@/components/common/PixelLoader.vue'
import { modelLifecycleUi } from '@/composable/modelLifecycleUi'

defineOptions({ name: 'ModelLifecycleOverlay' })

const props = defineProps<{ userId: string }>()
const models = ref<ManagedModelStatus[]>([])
const visibleKeys = ref(new Set<string>())
const confirmingKey = ref('')
const feedback = ref<Record<string, string>>({})
const completionTimers = new Map<string, ReturnType<typeof setTimeout>>()
let pollTimer: ReturnType<typeof setInterval> | null = null
let compactTimer: ReturnType<typeof setTimeout> | null = null

const notices = computed(() => models.value.filter(model => visibleKeys.value.has(model.key)))

/** Return whether the current model state represents active background work. */
function isWorking(model: ManagedModelStatus): boolean {
  return ['verifying', 'downloading', 'loading'].includes(model.status)
}

/** Collapse banners into the TopCommandBar loader five seconds after display. */
function scheduleCompact() {
  if (compactTimer) clearTimeout(compactTimer)
  compactTimer = setTimeout(() => {
    if (modelLifecycleUi.hasNotices) modelLifecycleUi.compact = true
  }, 5000)
}

/** Format real backend byte counts without fabricating totals. */
function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

/** Render the required verify → download → complete → verified lifecycle language. */
function lifecycleText(model: ManagedModelStatus): string {
  const label = model.label.replace(/\s*模型$/u, '')
  if (model.status === 'verifying') return `正在验证${label}模型`
  if (model.status === 'awaiting_download') return `${label}模型未下载`
  if (model.status === 'downloading') return `正在下载${label}模型`
  if (model.status === 'downloaded') return `下载${label}模型完成`
  if (model.status === 'loading' && model.progress.status === 'completed') {
    return `下载${label}模型完成，正在加载${label}模型`
  }
  if (model.status === 'loading') return `正在加载${label}模型`
  if (model.status === 'ready') return `${label}模型验证完成`
  return `${label}模型处理失败`
}

/** Keep each model notice independent and briefly retain terminal completion. */
function syncVisibility(nextModels: ManagedModelStatus[]) {
  const nextVisible = new Set(visibleKeys.value)
  for (const model of nextModels) {
    const active = ['verifying', 'awaiting_download', 'downloading', 'loading'].includes(model.status)
    if (active) {
      const timer = completionTimers.get(model.key)
      if (timer) clearTimeout(timer)
      completionTimers.delete(model.key)
      nextVisible.add(model.key)
      continue
    }
    if (!nextVisible.has(model.key) || completionTimers.has(model.key)) continue
    const timer = setTimeout(() => {
      const reduced = new Set(visibleKeys.value)
      reduced.delete(model.key)
      visibleKeys.value = reduced
      completionTimers.delete(model.key)
    }, 3000)
    completionTimers.set(model.key, timer)
  }
  visibleKeys.value = nextVisible
}

/** Poll the backend-owned states; this never blocks application navigation. */
async function refresh() {
  if (!props.userId) return
  try {
    const nextModels = (await fetchModelManagement(props.userId)).models
    models.value = nextModels
    syncVisibility(nextModels)
  } catch {
    // A transient status poll failure must not interfere with other business.
  }
}

/** Require a second explicit confirmation before any missing model download. */
async function confirmDownload(model: ManagedModelStatus) {
  if (!window.confirm(`确认下载 ${model.name}？下载大小由模型仓库决定。`)) return
  confirmingKey.value = model.key
  feedback.value = { ...feedback.value, [model.key]: '' }
  try {
    await downloadManagedModel(model.key, props.userId)
    await refresh()
  } catch (error: unknown) {
    feedback.value = {
      ...feedback.value,
      [model.key]: error instanceof Error ? error.message : '模型下载启动失败',
    }
  } finally {
    confirmingKey.value = ''
  }
}

watch(
  () => props.userId,
  (userId) => {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
    models.value = []
    visibleKeys.value = new Set()
    if (!userId) return
    void refresh()
    pollTimer = setInterval(refresh, 750)
  },
  { immediate: true },
)

watch(
  () => notices.value.length,
  (count, previousCount) => {
    modelLifecycleUi.hasNotices = count > 0
    if (count === 0) {
      modelLifecycleUi.compact = false
      if (compactTimer) clearTimeout(compactTimer)
      compactTimer = null
      return
    }
    if (previousCount === 0) {
      modelLifecycleUi.compact = true
    }
  },
  { immediate: true },
)

watch(
  () => modelLifecycleUi.expansionRequest,
  () => {
    if (!modelLifecycleUi.hasNotices) return
    modelLifecycleUi.compact = false
    scheduleCompact()
  },
)

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (compactTimer) clearTimeout(compactTimer)
  for (const timer of completionTimers.values()) clearTimeout(timer)
  modelLifecycleUi.compact = false
  modelLifecycleUi.hasNotices = false
})
</script>

<template>
  <aside v-if="notices.length && !modelLifecycleUi.compact" class="model-lifecycle-stack" aria-label="模型加载进度">
    <article v-for="model in notices" :key="model.key" class="model-lifecycle-notice" role="status" :data-model="model.key">
      <div class="notice-line">
        <span class="notice-indicator" :class="model.status"></span>
        <strong>{{ lifecycleText(model) }}</strong>
        <PixelLoader v-if="isWorking(model)" class="notice-loader" />
      </div>
      <div v-if="model.status === 'downloading'" class="notice-progress">
        <progress v-if="model.progress.percent !== null" :value="model.progress.percent" max="100"></progress>
        <progress v-else></progress>
        <span>
          {{ formatBytes(model.progress.downloaded_bytes) }}
          <template v-if="model.progress.total_bytes"> / {{ formatBytes(model.progress.total_bytes) }}</template>
        </span>
      </div>
      <button
        v-if="model.status === 'awaiting_download'"
        type="button"
        :disabled="confirmingKey === model.key"
        @click="confirmDownload(model)"
      >确认下载</button>
      <p v-if="feedback[model.key]" class="notice-error">{{ feedback[model.key] }}</p>
    </article>
  </aside>
</template>

<style scoped>
.model-lifecycle-stack {
  position: fixed;
  top: 72px;
  right: var(--space-16);
  z-index: 1200;
  display: grid;
  width: min(340px, calc(100vw - 32px));
  gap: var(--space-8);
  pointer-events: none;
}

.model-lifecycle-notice {
  padding: var(--space-10) var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
  color: var(--color-text);
  font-family: var(--font-ui);
  pointer-events: auto;
}

.notice-line {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.notice-line strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
}

.notice-loader {
  margin-left: auto;
  flex: 0 0 auto;
}

.notice-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
}

.notice-indicator.ready { background: var(--color-success); }
.notice-indicator.error { background: var(--color-danger); }

.notice-progress {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  margin-top: var(--space-8);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.notice-progress progress {
  width: 100%;
  height: 6px;
  accent-color: var(--color-primary);
}

.model-lifecycle-notice button {
  margin-top: var(--space-8);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
}

.model-lifecycle-notice button:disabled { opacity: 0.45; }
.notice-error { margin: var(--space-6) 0 0; color: var(--color-danger); font-size: calc(11px * var(--font-scale)); }

@media (max-width: 768px) {
  .model-lifecycle-stack {
    top: 68px;
    right: var(--space-8);
    bottom: auto;
    width: calc(100vw - 16px);
    max-height: calc(100vh - 76px);
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    overflow-y: auto;
    box-sizing: border-box;
  }

  .model-lifecycle-notice { padding: var(--space-8) var(--space-10); }
}
</style>
