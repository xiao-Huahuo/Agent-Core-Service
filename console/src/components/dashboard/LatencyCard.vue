<!--
  LatencyCard —— 每次 message 思考耗时折线图。
  点击数据点展开该轮步骤耗时占比（纵向柱状图 + 玫瑰图）。
  ECharts 渲染，弹性布局。
-->

<script setup>
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import { useObsData } from '@/composable/useObsData'

const obs = useObsData()
const selectedIdx = ref(-1)

const turns = computed(() => obs.latencyTurns.value)
const hasTurns = computed(() => turns.value.length > 0)

watch(turns, (val) => {
  if (val.length > 0) {
    selectedIdx.value = val.length - 1
  }
})

const summaryLabel = computed(() => {
  const s = obs.latencySummary.value
  if (turns.value.length === 0) return 'no data'
  return `avg ${s.avg}s · max ${s.max}s · ${turns.value.length} turns`
})
const emptyHint = computed(() => {
  const sessionId = obs.sessionStats.value.currentSessionId || '--'
  const messageCount = obs.messages.value.length
  return `$ no latency data | session ${sessionId} | messages ${messageCount}`
})

const selectedTurn = computed(() => {
  if (selectedIdx.value < 0 || selectedIdx.value >= turns.value.length) return null
  return turns.value[selectedIdx.value]
})

const ACCENT = '#d99178'
const LINE_COLOR = '#e8a880'
const POINT_FILL = '#1a1a2e'
const ACTIVE_FILL = '#d99178'
const GRID_COLOR = 'rgba(255,255,255,0.10)'
const TXT_LABEL = '#888'
const NODE_COLORS = ['#4da6ff', '#d99178', '#6ee7b7', '#a78bfa', '#f59e0b', '#f472b6', '#94a3b8']

function nodeColor(i) {
  return NODE_COLORS[i % NODE_COLORS.length]
}

const lineOption = computed(() => {
  const items = turns.value
  const sel = selectedIdx.value

  return {
    backgroundColor: 'transparent',
    grid: { top: 14, right: 20, bottom: 24, left: 42 },
    xAxis: {
      type: 'category',
      data: items.map((t) => `T${t.index}`),
      axisLine: { lineStyle: { color: GRID_COLOR } },
      axisTick: { show: false },
      axisLabel: { color: TXT_LABEL, fontSize: 9 },
    },
    yAxis: {
      type: 'value',
      name: '秒',
      min: 0,
      nameTextStyle: { color: TXT_LABEL, fontSize: 9 },
      splitLine: { lineStyle: { color: GRID_COLOR, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 9 },
    },
    series: [{
      type: 'line',
      data: items.map((t, i) => {
        const isSel = i === sel
        return {
          value: t.seconds,
          symbol: items.length === 1 ? 'pin' : 'circle',
          symbolSize: items.length === 1 ? 14 : (isSel ? 10 : 6),
          itemStyle: {
            color: isSel ? ACTIVE_FILL : POINT_FILL,
            borderColor: LINE_COLOR,
            borderWidth: 1.5,
          },
        }
      }),
      smooth: true,
      lineStyle: { color: LINE_COLOR, width: items.length === 1 ? 0 : 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${ACCENT}30` },
            { offset: 1, color: `${ACCENT}01` },
          ],
        },
      },
      emphasis: {
        scale: true,
        scaleSize: 3,
        focus: 'self',
      },
    }],
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `Turn ${p.dataIndex + 1}<br/>${p.value}s`
      },
    },
  }
})

/** 纵向柱状图 — 选中轮次的节点占比 */
const barOption = computed(() => {
  const turn = selectedTurn.value
  if (!turn || turn.nodeBreakdown.length === 0) return {}
  const items = turn.nodeBreakdown
  return {
    backgroundColor: 'transparent',
    grid: { top: 14, right: 8, bottom: 24, left: 30 },
    xAxis: {
      type: 'category',
      data: items.map((d) => d.node),
      axisLabel: { color: TXT_LABEL, fontSize: 7, rotate: items.length > 4 ? 30 : 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: GRID_COLOR, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 7, formatter: '{value}%' },
    },
    series: [{
      type: 'bar',
      data: items.map((d, i) => ({
        value: d.share,
        itemStyle: { color: nodeColor(i), borderRadius: [3, 3, 0, 0] },
      })),
      animationDuration: 800,
      animationEasing: 'cubicOut',
    }],
  }
})

/** 南丁格尔玫瑰图 — 选中轮次的节点占比 */
const roseOption = computed(() => {
  const turn = selectedTurn.value
  if (!turn || turn.nodeBreakdown.length === 0) return {}
  const items = turn.nodeBreakdown
  return {
    backgroundColor: 'transparent',
    legend: {
      bottom: 0,
      textStyle: { color: TXT_LABEL, fontSize: 7 },
      itemWidth: 8,
      itemHeight: 6,
      icon: 'roundRect',
    },
    series: [{
      type: 'pie',
      radius: '65%',
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 2 },
      label: { show: false },
      data: items.map((d, i) => ({
        name: d.node,
        value: d.share,
        itemStyle: { color: nodeColor(i) },
      })),
      animationDuration: 800,
    }],
  }
})

function onLineClick(params) {
  if (hasTurns.value && params.componentType === 'series') {
    const idx = params.dataIndex
    selectedIdx.value = selectedIdx.value === idx ? -1 : idx
  }
}
</script>

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">每次 message 思考耗时</span>
      <span class="window-status">{{ summaryLabel }}</span>
    </div>

    <div class="card-body">
      <div class="line-chart-wrap">
        <v-chart
          v-if="hasTurns"
          :option="lineOption"
          autoresize
          class="line-chart"
          @click="onLineClick"
        />
        <div v-else class="line-chart-skeleton" aria-hidden="true">
          <svg class="line-skeleton-svg" viewBox="0 0 100 60" preserveAspectRatio="none">
            <line x1="12" y1="6" x2="12" y2="50" class="axis-line" />
            <line x1="12" y1="50" x2="96" y2="50" class="axis-line" />
            <line x1="12" y1="16" x2="96" y2="16" class="grid-line" />
            <line x1="12" y1="28" x2="96" y2="28" class="grid-line" />
            <line x1="12" y1="40" x2="96" y2="40" class="grid-line" />
            <text x="2" y="17" class="axis-text">1</text>
            <text x="2" y="29" class="axis-text">0.5</text>
            <text x="5" y="41" class="axis-text">0</text>
            <text x="15" y="57" class="axis-text">T1</text>
            <text x="43" y="57" class="axis-text">T2</text>
            <text x="71" y="57" class="axis-text">T3</text>
            <polyline points="18,42 44,31 70,35 90,20" class="ghost-line" />
            <circle cx="18" cy="42" r="1.8" class="ghost-dot" />
            <circle cx="44" cy="31" r="1.8" class="ghost-dot" />
            <circle cx="70" cy="35" r="1.8" class="ghost-dot" />
            <circle cx="90" cy="20" r="1.8" class="ghost-dot" />
          </svg>
        </div>
      </div>

      <div v-if="selectedTurn" class="detail-panel">
        <div class="detail-summary">
          <span class="detail-title">Turn {{ selectedTurn.index }}</span>
          <span class="detail-time">{{ selectedTurn.seconds }}s{{ selectedTurn.estimated ? ' (est.)' : '' }}</span>
        </div>
        <p class="detail-prompt">{{ selectedTurn.userPrompt }}</p>

        <div v-if="selectedTurn.nodeBreakdown.length > 0" class="breakdown-charts">
          <div class="breakdown-col">
            <span class="col-label">步骤占比（柱状）</span>
            <v-chart :option="barOption" autoresize class="breakdown-chart" />
          </div>
          <div class="breakdown-col">
            <span class="col-label">步骤占比（玫瑰）</span>
            <v-chart :option="roseOption" autoresize class="breakdown-chart" />
          </div>
        </div>
      </div>

      <div v-else-if="turns.length > 0" class="no-selection">
        <span class="placeholder-text">$ 点击上方数据点查看各步骤耗时占比</span>
      </div>

      <div v-else class="empty-state">
        <span class="placeholder-text">{{ emptyHint }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-block {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: var(--shadow-window);
}

.card-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  padding: var(--space-8) var(--space-10);
  overflow-y: auto;
}

/* ---- 折线图 ---- */
.line-chart-wrap {
  flex-shrink: 0;
  height: 150px;
  min-height: 150px;
  border-bottom: 1px solid var(--color-border);
}

.line-chart {
  width: 100%;
  height: 100%;
  min-height: 100px;
}

.line-chart-skeleton {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: stretch;
}

.line-skeleton-svg {
  width: 100%;
  height: 100%;
}

.axis-line {
  stroke: var(--color-border-strong);
  stroke-width: 1;
}

.grid-line {
  stroke: var(--color-border);
  stroke-width: 1;
  stroke-dasharray: 2 2;
}

.axis-text {
  fill: var(--color-text-secondary);
  font-size: 4px;
  font-family: var(--font-mono);
}

.ghost-line {
  fill: none;
  stroke: rgba(217, 145, 120, 0.6);
  stroke-width: 1.5;
}

.ghost-dot {
  fill: rgba(217, 145, 120, 0.8);
}

/* ---- 明细面板 ---- */
.detail-panel {
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--space-8);
  flex-shrink: 0;
  min-height: 0;
  overflow: hidden;
}

.detail-summary {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-bottom: var(--space-4);
}

.detail-title {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-primary);
}

.detail-time {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-accent);
  margin-left: auto;
}

.detail-prompt {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0 0 var(--space-8);
  max-height: 48px;
  overflow: hidden;
}

/* ---- 步骤占比 ---- */
.breakdown-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-10);
}

@media (max-width: 480px) {
  .breakdown-charts {
    grid-template-columns: 1fr;
  }
}

.breakdown-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.col-label {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-4);
  flex-shrink: 0;
}

.breakdown-chart {
  width: 100%;
  height: 130px;
  min-height: 0;
  flex-shrink: 1;
}

/* ---- 提示 / 空状态 ---- */
.no-selection {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-10);
  border: 1px dashed var(--color-border);
  flex: 1;
  min-height: 0;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--color-border);
  min-height: 72px;
}

.placeholder-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
</style>
