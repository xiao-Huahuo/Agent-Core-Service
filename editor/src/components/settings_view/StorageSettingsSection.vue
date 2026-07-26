<!--
  存储管理设置区域组件。

  Usage:
    展示运行时目录树、ECharts 饼图和大小统计，支持路径编辑和清空操作。
    <StorageSettingsSection />
-->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import { FolderOpen, RefreshCw, ChevronRight } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { API_ROUTES } from '@/router/api_routes'

interface StoragePathEntry {
  key: string
  label: string
  value: string
  size_bytes: number
  requires_restart: boolean
  can_clear: boolean
  parent: string | null
}

interface StorageConfigResponse {
  paths: StoragePathEntry[]
  knowledge_dir_total_bytes: number
  runtime_total_bytes: number
}

interface ModelStatusData {
  embedding: string
  rerank: string
  paddleocr: string
}

const MODEL_KEYS = ['embedding_model_dir', 'paddleocr_model_dir', 'rerank_model_dir'] as const

const settingsStore = useSettingsStore()

const paths = ref<StoragePathEntry[]>([])
const knowledgeDirTotal = ref(0)
const runtimeTotal = ref(0)
const loading = ref(false)
const clearing = ref<string | null>(null)
const savingKey = ref<string | null>(null)
const feedback = ref('')
const knowledgeDirDraft = ref('')
const libraryStorageDirDraft = ref('')
const baseDataDirDraft = ref('')

/* ---- 模型状态 ---- */
const modelStatus = ref<ModelStatusData>({ embedding: 'unknown', rerank: 'unknown', paddleocr: 'unknown' })
const modelDownloading = ref<Set<string>>(new Set())
const modelProgress = ref<Record<string, number>>({})

function modelStatusText(model: string): string {
  const s = modelStatus.value[model as keyof ModelStatusData]
  if (modelDownloading.value.has(model)) {
    const pct = modelProgress.value[model]
    if (pct !== undefined && pct > 0) return `下载中 ${pct}%`
    return '下载中...'
  }
  switch (s) {
    case 'ready': return '已就绪'
    case 'downloaded': return '已下载'
    case 'downloading': return '下载中...'
    case 'loading': return '加载中...'
    case 'error': return '下载失败'
    case 'not_downloaded': return '未下载'
    default: return '未知'
  }
}

function modelStatusClass(model: string): string {
  const s = modelStatus.value[model as keyof ModelStatusData]
  if (s === 'ready') return 'status-ready'
  if (s === 'downloaded') return 'status-downloaded'
  if (s === 'downloading' || modelDownloading.value.has(model)) return 'status-downloading'
  if (s === 'loading') return 'status-loading'
  if (s === 'error') return 'status-error'
  if (s === 'not_downloaded') return 'status-missing'
  return 'status-unknown'
}

async function checkAllModels() {
  try {
    const res = await fetch(API_ROUTES.SETTINGS_MODEL_CHECK, { method: 'POST' })
    if (res.ok) {
      modelStatus.value = await res.json()
    }
  } catch { /* ignore */ }
}

async function pollModelStatus() {
  try {
    const res = await fetch(`${API_ROUTES.SETTINGS_MODEL_STATUS}?t=${Date.now()}`)
    if (res.ok) {
      modelStatus.value = await res.json()
    }
  } catch { /* ignore */ }
}

function modelKeyToType(modelDirKey: string): string {
  if (modelDirKey === 'embedding_model_dir') return 'embedding'
  if (modelDirKey === 'paddleocr_model_dir') return 'paddleocr'
  if (modelDirKey === 'rerank_model_dir') return 'rerank'
  return ''
}

function isModelReady(modelDirKey: string): boolean {
  const t = modelKeyToType(modelDirKey)
  return modelStatus.value[t as keyof ModelStatusData] === 'ready'
}

function shouldShowDownloadButton(modelDirKey: string): boolean {
  const t = modelKeyToType(modelDirKey)
  const s = modelStatus.value[t as keyof ModelStatusData]
  // 已下载、加载中、已就绪时都不显示下载按钮
  return s === 'not_downloaded' || s === 'error' || s === '' || s === 'unknown'
}

async function triggerDownload(modelDirKey: string) {
  const modelType = modelKeyToType(modelDirKey)
  if (!modelType) return
  modelDownloading.value = new Set([...modelDownloading.value, modelType])
  modelProgress.value = { ...modelProgress.value, [modelType]: 0 }

  // 假进度：缓缓爬到 64% 后等待
  let fakePct = 0
  const fakeInterval = setInterval(() => {
    if (fakePct < 64) {
      fakePct += Math.random() * 4 + 0.5
      if (fakePct > 64) fakePct = 64
      modelProgress.value = { ...modelProgress.value, [modelType]: Math.round(fakePct) }
    }
  }, 600)

  const interval = setInterval(async () => {
    await pollModelStatus()
    const s = modelStatus.value[modelType as keyof ModelStatusData]

    if (s === 'downloaded') {
      modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
      await triggerLoad(modelType)
      // 加载已触发，切换到只观察状态变化，不再重复触发的轮询
      clearInterval(interval)
      const watchInterval = setInterval(async () => {
        await pollModelStatus()
        const st = modelStatus.value[modelType as keyof ModelStatusData]
        if (st === 'ready') {
          modelProgress.value = { ...modelProgress.value, [modelType]: 100 }
          clearInterval(fakeInterval)
          setTimeout(() => {
            modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
          }, 300)
          clearInterval(watchInterval)
          show(`${modelType} 模型已就绪`)
          await loadStorageConfig()
          await checkAllModels()
        } else if (st === 'error') {
          clearInterval(fakeInterval)
          clearInterval(watchInterval)
          modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
          show(`${modelType} 模型加载失败`)
        }
      }, 1500)
    } else if (s === 'loading') {
      modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
    } else if (s === 'ready') {
      modelProgress.value = { ...modelProgress.value, [modelType]: 100 }
      clearInterval(fakeInterval)
      setTimeout(() => {
        modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
      }, 300)
      clearInterval(interval)
      show(`${modelType} 模型已就绪`)
      await loadStorageConfig()
      await checkAllModels()
    } else if (s === 'error') {
      clearInterval(fakeInterval)
      clearInterval(interval)
      modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
      show(`${modelType} 模型下载失败`)
    }
  }, 1500)

  try {
    const res = await fetch(API_ROUTES.SETTINGS_MODEL_DOWNLOAD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelType }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  } catch (e: unknown) {
    clearInterval(fakeInterval)
    clearInterval(interval)
    modelDownloading.value = new Set([...modelDownloading.value].filter(m => m !== modelType))
    show(e instanceof Error ? e.message : '下载启动失败')
  }
}

async function triggerLoad(modelType: string) {
  try {
    await fetch(API_ROUTES.SETTINGS_MODEL_LOAD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelType }),
    })
  } catch { /* ignore */ }
}

async function handleClickModel(modelDirKey: string) {
  const modelType = modelKeyToType(modelDirKey)
  if (!modelType) return
  const s = modelStatus.value[modelType as keyof ModelStatusData]
  if (s === 'downloaded') {
    // 立即本地设为 loading 显示 spinner
    modelStatus.value = { ...modelStatus.value, [modelType]: 'loading' as any }
    show(`${modelType} 模型加载中...`)
    await triggerLoad(modelType)
    // 轮询跟踪真实状态
    const poll = setInterval(async () => {
      await pollModelStatus()
      const st = modelStatus.value[modelType as keyof ModelStatusData]
      if (st === 'loading') {
        show(`${modelType} 模型加载中...`)
      } else if (st === 'ready') {
        show(`${modelType} 模型已就绪`)
        clearInterval(poll)
      } else if (st === 'error') {
        show(`${modelType} 模型加载失败`, 4000)
        clearInterval(poll)
      }
    }, 1500)
  }
}

async function pollModelProgress() {
  try {
    const res = await fetch(API_ROUTES.SETTINGS_MODEL_DOWNLOAD_PROGRESS)
    if (res.ok) {
      modelProgress.value = await res.json()
    }
  } catch { /* ignore */ }
}

/* ---- 颜色板：主色/点缀色/语义色 ---- */
const PIE_COLORS = [
  '#4224eb', '#eb2463', '#26a269', '#e2a72e', '#ef4444',
]

/* ---- 排序 ---- */
const ROOT_ORDER = [
  'knowledge_dir', 'library_storage_dir', 'base_data_dir',
  'assets_dir', 'db_dir', 'relation_db_dir', 'vector_db_dir', 'sqlite_path', 'chroma_persist_dir',
  'frontmatter_dir', 'log_dir', 'models_dir',
  'embedding_model_dir', 'paddleocr_model_dir', 'rerank_model_dir',
  'trash_dir',
]

interface TreeItem {
  entry: StoragePathEntry
  depth: number
  hasChildren: boolean
}

const collapsedKeys = ref<Set<string>>(new Set())

function hasChild(key: string): boolean {
  return paths.value.some(p => p.parent === key)
}

function sortedChildren(parentKey: string): StoragePathEntry[] {
  return paths.value
    .filter(p => p.parent === parentKey)
    .sort((a, b) => ROOT_ORDER.indexOf(a.key) - ROOT_ORDER.indexOf(b.key))
}

const rootPaths = computed(() =>
  paths.value
    .filter(p => !p.parent)
    .sort((a, b) => ROOT_ORDER.indexOf(a.key) - ROOT_ORDER.indexOf(b.key))
)

const treeItems = computed(() => {
  const items: TreeItem[] = []
  function walk(parentKey: string, depth: number, parentCollapsed: boolean) {
    for (const child of sortedChildren(parentKey)) {
      if (parentCollapsed) return
      const hc = hasChild(child.key)
      const isCollapsed = collapsedKeys.value.has(child.key)
      items.push({ entry: child, depth, hasChildren: hc })
      walk(child.key, depth + 1, isCollapsed)
    }
  }
  for (const root of rootPaths.value) {
    const hc = hasChild(root.key)
    const isCollapsed = collapsedKeys.value.has(root.key)
    items.push({ entry: root, depth: 0, hasChildren: hc })
    walk(root.key, 1, isCollapsed)
  }
  return items
})

function toggleCollapse(key: string) {
  const next = new Set(collapsedKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedKeys.value = next
}

function formatMB(bytes: number): string {
  if (bytes === 0) return '0 MB'
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`
}

/* ---- 饼图数据 ---- */
const totalPieOption = computed(() => ({
  tooltip: {
    trigger: 'item' as const,
    backgroundColor: 'rgba(30,30,40,0.92)',
    borderColor: 'rgba(255,255,255,0.08)',
    textStyle: { color: '#ccc', fontSize: 12 },
    formatter: (p: { name: string; value: number; percent: number }) =>
      `${p.name}: ${formatMB(p.value)} (${p.percent}%)`,
  },
  series: [{
    type: 'pie',
    radius: '65%',
    center: ['50%', '50%'],
    emphasis: { label: { fontWeight: 'bold' } },
    label: { show: false },
    data: [
      { name: '知识库', value: knowledgeDirTotal.value, itemStyle: { color: '#4224eb' } },
      { name: '运行时', value: runtimeTotal.value, itemStyle: { color: '#eb2463' } },
    ].filter(d => d.value > 0),
  }],
}))

const runtimePieData = computed(() =>
  (runtimePieOption.value as any)?.series?.[0]?.data as { name: string; value: number }[] | undefined
)

const runtimePieOption = computed(() => {
  const entries = paths.value
    .filter(p => p.key !== 'knowledge_dir' && p.key !== 'base_data_dir' && p.parent === 'base_data_dir')
    .filter(p => p.size_bytes > 0)
  return {
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(30,30,40,0.92)',
      borderColor: 'rgba(255,255,255,0.08)',
      textStyle: { color: '#ccc', fontSize: 12 },
      formatter: (p: { name: string; value: number; percent: number }) =>
        `${p.name}: ${formatMB(p.value)} (${p.percent}%)`,
    },
    series: [{
      type: 'pie',
      radius: '65%',
      center: ['50%', '50%'],
      emphasis: { label: { fontWeight: 'bold' } },
      label: { show: false },
      data: entries.map((e, i) => ({
        name: e.label,
        value: e.size_bytes,
        itemStyle: { color: PIE_COLORS[i % PIE_COLORS.length] },
      })),
    }],
  }
})

/* ---- 工具函数 ---- */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function openInExplorer(absPath: string) {
  window.agentEditorDesktop?.openPath?.(absPath)
}

function show(msg: string, ms = 2000) {
  feedback.value = msg
  setTimeout(() => { feedback.value = '' }, ms)
}

/* ---- API ---- */
async function loadStorageConfig() {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    const res = await fetch(`${API_ROUTES.SETTINGS_STORAGE_CONFIG}?user_id=${encodeURIComponent(settingsStore.profile.userId)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data: StorageConfigResponse = await res.json()
    paths.value = data.paths
    knowledgeDirTotal.value = data.knowledge_dir_total_bytes
    runtimeTotal.value = data.runtime_total_bytes

    const kd = data.paths.find((p: StoragePathEntry) => p.key === 'knowledge_dir')
    if (kd) knowledgeDirDraft.value = kd.value
    const ld = data.paths.find((p: StoragePathEntry) => p.key === 'library_storage_dir')
    if (ld) libraryStorageDirDraft.value = ld.value
    const rd = data.paths.find((p: StoragePathEntry) => p.key === 'base_data_dir')
    if (rd) baseDataDirDraft.value = rd.value
  } catch {
    show('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveLibraryStorageDir() {
  if (savingKey.value) return
  savingKey.value = 'library_storage_dir'
  feedback.value = ''
  try {
    const body = JSON.stringify({
      user_id: settingsStore.profile.userId,
      paths: { library_storage_dir: libraryStorageDirDraft.value },
    })
    const res = await fetch(API_ROUTES.SETTINGS_STORAGE_CONFIG, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body,
    })
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(detail || `HTTP ${res.status}`)
    }
    await settingsStore.refreshUserProfile()
    show('图书馆存储路径已更新')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : '保存失败', 4000)
  } finally {
    savingKey.value = null
    await loadStorageConfig()
  }
}

async function handleSaveKnowledgeDir() {
  if (savingKey.value) return
  savingKey.value = 'knowledge_dir'
  feedback.value = ''
  try {
    await settingsStore.switchKnowledgeRoot(knowledgeDirDraft.value)
    show('知识库路径已更新')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingKey.value = null
    await loadStorageConfig()
  }
}

async function handleSaveBaseDataDir() {
  if (savingKey.value) return
  savingKey.value = 'base_data_dir'
  feedback.value = ''
  try {
    const body = JSON.stringify({
      user_id: settingsStore.profile.userId,
      paths: { base_data_dir: baseDataDirDraft.value },
    })
    const res = await fetch(API_ROUTES.SETTINGS_STORAGE_CONFIG, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    show('运行时根路径已保存，重启后生效')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingKey.value = null
    await loadStorageConfig()
  }
}

async function handleClear(pathKey: string, label: string) {
  const confirmed = window.confirm(`确认清空 "${label}"？此操作不可撤销。`)
  if (!confirmed) return
  clearing.value = pathKey
  feedback.value = ''
  try {
    const res = await fetch(API_ROUTES.SETTINGS_STORAGE_CLEAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path_key: pathKey }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    show(`已清空，释放 ${formatBytes(data.freed_bytes)}`)
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : '操作失败')
  } finally {
    clearing.value = null
    await loadStorageConfig()
    await checkAllModels()
  }
}

onMounted(() => {
  loadStorageConfig()
  checkAllModels()
})
</script>

<template>
  <div class="setting-section">
    <div class="section-header">
      <h3>存储管理</h3>
      <button class="icon-btn" :disabled="loading" title="刷新统计" @click="loadStorageConfig">
        <RefreshCw :size="15" :class="{ spinning: loading }" />
      </button>
    </div>

    <!-- 统计概览：左数字 / 右饼图 -->
    <div class="stats-row">
      <!-- 左侧：数字 -->
      <div class="stats-left">
        <div class="stat-card">
          <div class="stat-card-dot knowledge-dot"></div>
          <span class="stat-card-label">知识库</span>
          <span class="stat-card-value">{{ formatBytes(knowledgeDirTotal) }}</span>
        </div>
        <div class="stat-card">
          <div class="stat-card-dot runtime-dot"></div>
          <span class="stat-card-label">运行时</span>
          <span class="stat-card-value">{{ formatBytes(runtimeTotal) }}</span>
        </div>
      </div>

      <!-- 右侧：饼图 + 图例 -->
      <div v-if="paths.length > 0" class="stats-right">
        <div class="pie-charts">
          <div class="pie-chart-item">
            <VChart class="pie-canvas" :option="totalPieOption" autoresize />
            <span class="pie-title">知识库 / 运行时</span>
          </div>
          <div class="pie-chart-item">
            <VChart class="pie-canvas" :option="runtimePieOption" autoresize />
            <span class="pie-title">运行时分布</span>
          </div>
        </div>
        <div v-if="(runtimePieData?.length ?? 0) > 1" class="pie-legend">
          <span v-for="(item, i) in runtimePieData ?? []" :key="String(item.name)" class="legend-item">
            <span class="legend-dot" :style="{ background: PIE_COLORS[i % PIE_COLORS.length] }"></span>
            {{ item.name }}
          </span>
        </div>
      </div>
    </div>

    <p v-if="feedback" class="feedback">{{ feedback }}</p>

    <!-- 路径树 -->
    <div v-if="paths.length > 0" class="storage-tree">
      <div>
        <template v-for="item in treeItems" :key="item.entry.key">
          <div class="tree-row" :class="{ 'tree-child': item.depth > 0 }">
            <div class="tree-label-cell" :style="{ paddingLeft: `${item.depth * 20}px` }">
              <button
                v-if="item.hasChildren"
                class="tree-collapse-btn"
                @click="toggleCollapse(item.entry.key)"
              >
                <ChevronRight :size="13" :class="{ rotated: !collapsedKeys.has(item.entry.key) }" />
              </button>
              <span v-else class="tree-spacer"></span>
              <span class="tree-name" :class="{ 'child-name': item.depth > 0 }">{{ item.entry.label }}</span>
            </div>
            <div class="tree-value-cell">
              <template v-if="item.depth === 0 && item.entry.key === 'knowledge_dir'">
                <input v-model="knowledgeDirDraft" type="text" class="tree-input" :disabled="savingKey === item.entry.key" />
                <button class="tree-explore-btn" title="在资源管理器中打开" @click="openInExplorer(item.entry.value)">
                  <FolderOpen :size="14" />
                </button>
                <button class="save-model-btn" :disabled="savingKey === item.entry.key || knowledgeDirDraft === item.entry.value" @click="handleSaveKnowledgeDir">
                  {{ savingKey === item.entry.key ? '...' : '保存' }}
                </button>
              </template>
              <template v-else-if="item.entry.key === 'library_storage_dir'">
                <input v-model="libraryStorageDirDraft" type="text" class="tree-input" :disabled="savingKey === item.entry.key" />
                <button class="tree-explore-btn" title="在资源管理器中打开" @click="openInExplorer(item.entry.value)">
                  <FolderOpen :size="14" />
                </button>
                <button class="save-model-btn" :disabled="savingKey === item.entry.key || libraryStorageDirDraft === item.entry.value" @click="handleSaveLibraryStorageDir">
                  {{ savingKey === item.entry.key ? '...' : '保存' }}
                </button>
              </template>
              <template v-else-if="item.depth === 0 && item.entry.key === 'base_data_dir'">
                <input v-model="baseDataDirDraft" type="text" class="tree-input" :disabled="savingKey === item.entry.key" />
                <button class="tree-explore-btn" title="在资源管理器中打开" @click="openInExplorer(item.entry.value)">
                  <FolderOpen :size="14" />
                </button>
                <button class="save-model-btn" :disabled="savingKey === item.entry.key || baseDataDirDraft === item.entry.value" @click="handleSaveBaseDataDir">
                  {{ savingKey === item.entry.key ? '...' : '保存（需重启）' }}
                </button>
              </template>
              <template v-else-if="MODEL_KEYS.includes(item.entry.key as any)">
                <span class="tree-value mono">{{ item.entry.value }}</span>
              </template>
              <template v-else>
                <span class="tree-value mono">{{ item.entry.value }}</span>
              </template>
            </div>
            <div class="tree-size-cell">{{ formatBytes(item.entry.size_bytes) }}</div>
            <div class="tree-action-cell">
              <template v-if="MODEL_KEYS.includes(item.entry.key as any) && !modelDownloading.has(modelKeyToType(item.entry.key))">
                <span
                  class="model-status-dot"
                  :class="[modelStatusClass(modelKeyToType(item.entry.key)), { clickable: modelStatus[modelKeyToType(item.entry.key) as keyof ModelStatusData] === 'downloaded' }]"
                  :title="modelStatusText(modelKeyToType(item.entry.key))"
                  @click="handleClickModel(item.entry.key)"
                ></span>
                <span
                  class="model-status-label"
                  :class="[modelStatusClass(modelKeyToType(item.entry.key)), { clickable: modelStatus[modelKeyToType(item.entry.key) as keyof ModelStatusData] === 'downloaded' }]"
                  @click="handleClickModel(item.entry.key)"
                >{{ modelStatusText(modelKeyToType(item.entry.key)) }}</span>
                <span v-if="modelStatus[modelKeyToType(item.entry.key) as keyof ModelStatusData] === 'loading'" class="model-loading-spinner"></span>
                <button
                  v-if="shouldShowDownloadButton(item.entry.key)"
                  class="save-model-btn"
                  :disabled="modelDownloading.has(modelKeyToType(item.entry.key))"
                  @click="triggerDownload(item.entry.key)"
                >
                  下载
                </button>
              </template>
              <template v-if="modelDownloading.has(modelKeyToType(item.entry.key))">
                <div class="model-progress-bar">
                  <div class="model-progress-fill" :style="{ width: `${modelProgress[modelKeyToType(item.entry.key)] || 0}%` }"></div>
                </div>
                <span class="model-progress-pct">{{ modelProgress[modelKeyToType(item.entry.key)] || 0 }}%</span>
              </template>
              <button
                v-if="item.entry.can_clear && item.entry.key !== 'frontmatter_dir'"
                class="delete-btn"
                :disabled="clearing === item.entry.key"
                :title="`清空 ${item.entry.label}`"
                @click="handleClear(item.entry.key, item.entry.label)"
              >
                <svg viewBox="0 0 448 512" class="svgIcon"><path d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64S14.3 96 32 96H416c17.7 0 32-14.3 32-32s-14.3-32-32-32H320l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32L53.2 467c1.6 25.3 22.6 45 47.9 45H346.9c25.3 0 46.3-19.7 47.9-45L416 128z"></path></svg>
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <p v-else-if="!loading" class="setting-hint">暂无存储路径数据</p>
  </div>
</template>

<style scoped>
/* ---- 页头：标题 + 刷新按钮 ---- */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-10);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color var(--transition-fast), color var(--transition-fast);
}

.icon-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinning {
  animation: spin 0.8s linear infinite;
}

/* ---- 统计概览：左右两栏 ---- */
.stats-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: var(--space-16);
  margin-bottom: var(--space-8);
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}

.stats-left {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.stats-right {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
}

/* ---- 数字卡片 ---- */
.stat-card {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  align-items: center;
  gap: var(--space-10);
  min-height: 58px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-10) var(--space-12);
  background: rgba(255, 255, 255, 0.02);
}

.stat-card-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.knowledge-dot {
  background: #4224eb;
}

.runtime-dot {
  background: #eb2463;
}

.stat-card-label {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-card-value {
  flex: 0 0 auto;
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

/* ---- 饼图 ---- */
.pie-charts {
  display: flex;
  gap: var(--space-12);
}

.pie-chart-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
}

.pie-canvas {
  width: 180px;
  height: 180px;
  flex-shrink: 0;
}

.pie-title {
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
}

/* 图例 */
.pie-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-4) var(--space-10);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ---- 路径树 ---- */
.storage-tree {
  position: relative;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.tree-row {
  display: grid;
  grid-template-columns: 200px 1fr 80px auto;
  align-items: center;
  gap: var(--space-10);
  padding: var(--space-6) var(--space-10);
  min-height: 44px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
}

@media (max-width: 768px) {
  .tree-row {
    grid-template-columns: 1fr;
    gap: var(--space-4);
  }
}

.tree-row:last-child {
  border-bottom: none;
}

.tree-child {
  background: var(--color-surface);
}

.tree-label-cell {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
}

.tree-collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--transition-fast);
}

.tree-collapse-btn:hover {
  color: var(--color-primary);
}

@keyframes chevron-rotate-in {
  from { transform: rotate(-90deg); }
  to   { transform: rotate(0deg); }
}

.tree-collapse-btn .rotated {
  animation: chevron-rotate-in 0.2s ease forwards;
}

.tree-spacer {
  display: inline-block;
  width: 18px;
  flex-shrink: 0;
}

.tree-name {
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.child-name {
  color: var(--color-text-secondary);
}

.tree-value-cell {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
}

.tree-value {
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-value.mono {
  font-family: var(--font-mono);
}

.tree-input {
  flex: 1;
  min-width: 0;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: calc(11px * var(--font-scale));
  outline: none;
}

.tree-input:focus {
  border-color: var(--color-primary);
}

.tree-input:disabled {
  opacity: 0.5;
}

.tree-explore-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.tree-explore-btn:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.tree-size-cell {
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text-muted);
  text-align: right;
  white-space: nowrap;
}

.tree-action-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-6);
  flex-shrink: 0;
}

/* ---- 模型状态指示 ---- */
.model-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.model-status-dot.status-ready { background: #26a269; }
.model-status-dot.status-downloading { background: #e2a72e; }
.model-status-dot.status-downloaded { background: #e2a72e; }
.model-status-dot.status-loading { background: #e2a72e; }
.model-status-dot.status-error { background: #ef4444; }
.model-status-dot.status-missing { background: #888; }
.model-status-dot.status-unknown { background: #555; }

.model-status-label {
  font-size: calc(11px * var(--font-scale));
  white-space: nowrap;
}
.model-status-label.status-ready { color: #26a269; }
.model-status-label.status-downloaded { color: #e2a72e; }
.model-status-label.status-downloading { color: #e2a72e; }
.model-status-label.status-loading { color: #e2a72e; }
.model-status-label.status-error { color: #ef4444; }
.model-status-label.status-missing { color: #888; }
.model-status-label.status-unknown { color: #555; }

.model-status-dot.clickable { cursor: pointer; }
.model-status-label.clickable { cursor: pointer; text-decoration: underline dotted; }

/* ---- 模型加载 spinner ---- */
.model-loading-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border);
  border-top-color: #e2a72e;
  border-radius: 50%;
  animation: model-loader-spin 0.7s linear infinite;
}

@keyframes model-loader-spin {
  to { transform: rotate(360deg); }
}

/* ---- 模型下载进度条 ---- */
.model-progress-bar {
  width: 80px;
  height: 6px;
  border-radius: 999px;
  background: var(--color-border);
  overflow: hidden;
  flex-shrink: 0;
}

.model-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--color-primary);
  transition: width 0.8s ease;
}

.model-progress-pct {
  font-size: calc(10px * var(--font-scale));
  color: var(--color-text-muted);
  white-space: nowrap;
  min-width: 32px;
  text-align: right;
}
</style>
