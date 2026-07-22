<!--
  TokenUsageCard -- persisted token usage charts.

  Usage:
  Keeps the original dashboard card area and switches between three backend
  backed charts: per model call, fixed time bucket, and session total usage.
-->

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import DashboardCardFrame from '@/components/dashboard/DashboardCardFrame.vue'
import { fetchTokenUsageStats } from '@/api/agent'
import type { TokenUsageInterval, TokenUsageStatsResponse } from '@/api/agent'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

type ChartKind = 'calls' | 'buckets' | 'sessions'
type ChartMode = 'bar' | 'line'

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const chartKind = ref<ChartKind>('buckets')
const chartModes = ref<Record<ChartKind, ChartMode>>({
  calls: 'line',
  buckets: 'bar',
  sessions: 'bar',
})
const interval = ref<TokenUsageInterval>('5m')
const loading = ref(false)
const error = ref('')
const stats = ref<TokenUsageStatsResponse>({
  interval: '5m',
  calls: [],
  buckets: [],
  sessions: [],
})

const chartTabs: Array<{ value: ChartKind; label: string }> = [
  { value: 'buckets', label: '时间刻度' },
  { value: 'calls', label: '每次调用' },
  { value: 'sessions', label: 'Session 总量' },
]

const intervalOptions: Array<{ value: TokenUsageInterval; label: string }> = [
  { value: '1m', label: '1分钟' },
  { value: '3m', label: '3分钟' },
  { value: '5m', label: '5分钟' },
  { value: '10m', label: '10分钟' },
  { value: '30m', label: '30分钟' },
  { value: '1h', label: '1小时' },
  { value: '2h', label: '2小时' },
  { value: '3h', label: '3小时' },
  { value: '6h', label: '6小时' },
  { value: '12h', label: '12小时' },
  { value: '24h', label: '24小时' },
  { value: '3d', label: '3天' },
  { value: '10d', label: '10天' },
  { value: '15d', label: '15天' },
  { value: 'month', label: '月' },
]

const CURVE_COLORS = {
  large: '#4da6ff',
  small: '#6ee7b7',
  total: '#d99178',
}
const BORDER = 'rgba(255,255,255,0.08)'
const TXT_LABEL = '#777'

const statusText = computed(() => {
  if (loading.value) return '读取中'
  if (error.value) return '读取失败'
  if (chartKind.value === 'calls') return `${stats.value.calls.length} 次调用`
  if (chartKind.value === 'buckets') return intervalOptions.find((item) => item.value === interval.value)?.label || interval.value
  return `${stats.value.sessions.length} sessions`
})

const hasData = computed(() => {
  if (chartKind.value === 'calls') return stats.value.calls.length > 0
  if (chartKind.value === 'buckets') return stats.value.buckets.length > 0
  return stats.value.sessions.some((session) => session.total_tokens > 0)
})

const activeOption = computed(() => {
  if (chartKind.value === 'calls') return callOption.value
  if (chartKind.value === 'buckets') return bucketOption.value
  return sessionOption.value
})

const activeChartMode = computed({
  get: () => chartModes.value[chartKind.value],
  set: (value: ChartMode) => {
    chartModes.value = { ...chartModes.value, [chartKind.value]: value }
  },
})

const callOption = computed(() => {
  const items = stats.value.calls
  const mode = chartModes.value.calls
  return baseOption({
    xData: items.map((item) => formatShortTime(item.created_at)),
    series: [
      tokenSeries('大模型', items.map((item) => item.model_tier === 'large' ? item.total_tokens : 0), CURVE_COLORS.large, mode),
      tokenSeries('小模型', items.map((item) => item.model_tier === 'small' ? item.total_tokens : 0), CURVE_COLORS.small, mode),
    ],
  })
})

const bucketOption = computed(() => {
  const items = stats.value.buckets
  const mode = chartModes.value.buckets
  return baseOption({
    xData: items.map((item) => item.label),
    series: [
      tokenSeries('大模型', items.map((item) => item.large_tokens), CURVE_COLORS.large, mode),
      tokenSeries('小模型', items.map((item) => item.small_tokens), CURVE_COLORS.small, mode),
    ],
  })
})

const sessionOption = computed(() => {
  const items = stats.value.sessions.filter((item) => item.total_tokens > 0).slice(0, 12)
  const mode = chartModes.value.sessions
  return baseOption({
    xData: items.map((item) => item.session_name || item.session_id),
    xRotate: items.length > 4 ? 25 : 0,
    series: [
      tokenSeries('大模型', items.map((item) => item.large_tokens), CURVE_COLORS.large, mode),
      tokenSeries('小模型', items.map((item) => item.small_tokens), CURVE_COLORS.small, mode),
    ],
  })
})

function tokenSeries(name: string, data: number[], color: string, mode: ChartMode) {
  if (mode === 'bar') {
    return {
      name,
      type: 'bar',
      stack: 'token',
      barMaxWidth: 18,
      data,
      itemStyle: {
        color,
        opacity: 0.82,
      },
      emphasis: {
        itemStyle: {
          opacity: 1,
        },
      },
    }
  }
  return {
    name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 5,
    data,
    lineStyle: {
      color,
      width: 1.8,
      shadowBlur: 10,
      shadowColor: `${color}99`,
    },
    itemStyle: {
      color,
      shadowBlur: 8,
      shadowColor: `${color}88`,
    },
    areaStyle: gradientArea(color),
    emphasis: {
      lineStyle: {
        width: 2.4,
        shadowBlur: 16,
      },
    },
  }
}

function gradientArea(color: string) {
  return {
    color: {
      type: 'linear',
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: `${color}5c` },
        { offset: 0.45, color: `${color}24` },
        { offset: 1, color: `${color}02` },
      ],
    },
    shadowBlur: 18,
    shadowColor: `${color}66`,
  }
}

function baseOption({ xData, series, xRotate = 0 }: { xData: string[]; series: unknown[]; xRotate?: number }) {
  return {
    backgroundColor: 'transparent',
    grid: { top: 14, right: 16, bottom: 28, left: 42 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: BORDER } },
      axisTick: { show: false },
      axisLabel: {
        color: TXT_LABEL,
        fontSize: 7,
        rotate: xRotate || (xData.length > 8 ? 30 : 0),
        overflow: 'truncate',
      },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: BORDER, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 8 },
    },
    series,
    legend: {
      bottom: 0,
      textStyle: { color: TXT_LABEL, fontSize: 9 },
      itemWidth: 10,
      itemHeight: 6,
      icon: 'roundRect',
    },
    tooltip: { trigger: 'axis' },
  }
}

function formatShortTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function loadStats() {
  const userId = settingsStore.profile.userId
  if (!userId) {
    stats.value = { interval: interval.value, calls: [], buckets: [], sessions: [] }
    return
  }
  loading.value = true
  error.value = ''
  try {
    stats.value = await fetchTokenUsageStats(userId, {
      sessionId: sessionStore.currentSessionId,
      interval: interval.value,
      limit: 120,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取 token 统计失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadStats()
})

watch(
  () => [settingsStore.profile.userId, sessionStore.currentSessionId, interval.value] as const,
  () => void loadStats(),
)

watch(
  () => chatStore.isStreaming,
  (streaming, wasStreaming) => {
    if (!streaming && wasStreaming) {
      void loadStats()
    }
  },
)
</script>

<template>
  <DashboardCardFrame title="Token 用量" :status="statusText">
    <div class="card-body">
      <div class="chart-toolbar">
        <button
          v-for="tab in chartTabs"
          :key="tab.value"
          class="chart-mode-btn"
          :class="{ active: chartKind === tab.value }"
          type="button"
          @click="chartKind = tab.value"
        >
          {{ tab.label }}
        </button>
        <select v-if="chartKind === 'buckets'" v-model="interval" class="interval-select">
          <option v-for="option in intervalOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <div class="chart-type-toggle">
          <button
            class="chart-mode-btn"
            :class="{ active: activeChartMode === 'bar' }"
            type="button"
            @click="activeChartMode = 'bar'"
          >
            柱状图
          </button>
          <button
            class="chart-mode-btn"
            :class="{ active: activeChartMode === 'line' }"
            type="button"
            @click="activeChartMode = 'line'"
          >
            曲线图
          </button>
        </div>
      </div>

      <div v-if="hasData" class="chart-area">
        <v-chart :option="activeOption" autoresize class="chart-box" />
      </div>
      <div v-else class="empty-state">
        <span class="placeholder-text">{{ error || '等待 token 统计' }}</span>
      </div>
    </div>
  </DashboardCardFrame>
</template>

<style scoped>
.card-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  padding: var(--space-8) var(--space-10);
  overflow: hidden;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-shrink: 0;
}

.chart-type-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-left: auto;
}

.chart-mode-btn,
.interval-select {
  height: 22px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(9px * var(--font-scale));
}

.chart-mode-btn {
  padding: 0 8px;
  cursor: pointer;
}

.chart-mode-btn.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-softer);
}

.interval-select {
  padding: 0 6px;
  border-color: var(--color-border);
  background: var(--color-surface);
}

.chart-area {
  flex: 1;
  min-height: 0;
}

.chart-box {
  width: 100%;
  height: 100%;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
}

.placeholder-text {
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}
</style>
