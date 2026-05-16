<!--
  TokenUsageCard —— 按时刻和模型的 token 用量变化。
  可切换柱状图 / 曲线图，ECharts 渲染，弹性布局。
-->

<script setup>
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import { useObsData } from '@/composable/useObsData'

const obs = useObsData()
const chartMode = ref('line')

const CURVE_COLORS = ['#4da6ff', '#d99178', '#6ee7b7', '#a78bfa', '#f59e0b']
const BORDER = 'rgba(255,255,255,0.08)'
const TXT_LABEL = '#777'
const TXT_PRIMARY = '#e0e0e0'

function curveColor(_, i) {
  return CURVE_COLORS[i % CURVE_COLORS.length]
}

const modelNames = computed(() => {
  const names = []
  const seen = new Set()
  for (const item of obs.tokenSeries.value) {
    for (const name of Object.keys(item.modelTokens)) {
      if (!seen.has(name)) { seen.add(name); names.push(name) }
    }
  }
  return names
})

const modelTotals = computed(() => {
  const last = obs.tokenSeries.value[obs.tokenSeries.value.length - 1]
  return last?.modelTotals || {}
})

/** 折线图 option */
const lineOption = computed(() => {
  const items = obs.tokenSeries.value
  const names = modelNames.value
  return {
    backgroundColor: 'transparent',
    grid: { top: 14, right: 16, bottom: 28, left: 40 },
    xAxis: {
      type: 'category',
      data: items.map((d) => d.label),
      axisLine: { lineStyle: { color: BORDER } },
      axisTick: { show: false },
      axisLabel: { color: TXT_LABEL, fontSize: 7, rotate: items.length > 8 ? 30 : 0 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: BORDER, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 8 },
    },
    series: names.map((name, i) => ({
      name,
      type: 'line',
      data: items.map((d) => d.modelTokens[name] || 0),
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: curveColor(name, i), width: 1.6 },
      itemStyle: { color: curveColor(name, i) },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${curveColor(name, i)}30` },
            { offset: 1, color: `${curveColor(name, i)}03` },
          ],
        },
      },
    })),
    legend: {
      bottom: 0,
      textStyle: { color: TXT_LABEL, fontSize: 9 },
      itemWidth: 10,
      itemHeight: 6,
      icon: 'roundRect',
    },
    tooltip: { trigger: 'axis' },
  }
})

/** 柱状图 option */
const barOption = computed(() => {
  const items = obs.tokenSeries.value
  const names = modelNames.value
  return {
    backgroundColor: 'transparent',
    grid: { top: 14, right: 16, bottom: 28, left: 40 },
    xAxis: {
      type: 'category',
      data: items.map((d) => d.label),
      axisLabel: { color: TXT_LABEL, fontSize: 7, rotate: items.length > 8 ? 30 : 0 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: BORDER, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 8 },
    },
    series: names.map((name, i) => ({
      name,
      type: 'bar',
      stack: 'total',
      data: items.map((d) => d.modelTokens[name] || 0),
      itemStyle: { color: curveColor(name, i) },
      emphasis: { focus: 'series' },
    })),
    legend: {
      bottom: 0,
      textStyle: { color: TXT_LABEL, fontSize: 9 },
      itemWidth: 10,
      itemHeight: 6,
      icon: 'roundRect',
    },
    tooltip: { trigger: 'axis' },
  }
})
</script>

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">按时刻和模型的 token 用量变化</span>
      <span class="window-status">{{ modelNames.join(' + ') || 'idle' }}</span>
    </div>

    <div class="card-body">
      <div class="chart-toolbar">
        <button class="chart-mode-btn" :class="{ active: chartMode === 'bar' }" @click="chartMode = 'bar'">柱状图</button>
        <button class="chart-mode-btn" :class="{ active: chartMode === 'line' }" @click="chartMode = 'line'">曲线图</button>
      </div>

      <!-- 模型累计 -->
      <div class="totals" :style="{ gridTemplateColumns: `repeat(${Math.max(1, modelNames.length)}, minmax(0, 1fr))` }">
        <div v-for="(name, i) in modelNames" :key="name" class="total-box">
          <span class="total-label" :style="{ color: curveColor(name, i) }">{{ name }}</span>
          <span class="total-value">{{ modelTotals[name] || 0 }}</span>
        </div>
        <div v-if="modelNames.length === 0" class="total-box">
          <span class="total-label">--</span>
          <span class="total-value">0</span>
        </div>
      </div>

      <div v-if="obs.tokenSeries.value.length > 0" class="chart-area">
        <v-chart v-if="chartMode === 'line'" :option="lineOption" autoresize class="chart-box" />
        <v-chart v-else :option="barOption" autoresize class="chart-box" />
      </div>

      <div v-else class="empty-state">
        <span class="placeholder-text">$ 等待消息生成 token 统计</span>
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
  overflow: hidden;
}

.chart-toolbar {
  display: flex;
  gap: var(--space-6);
  flex-shrink: 0;
}

.chart-mode-btn {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  cursor: pointer;
}
.chart-mode-btn:hover { color: var(--color-text-secondary); background: var(--color-bg-hover); }
.chart-mode-btn.active { color: var(--color-blue); border-color: rgba(77,166,255,0.3); background: rgba(77,166,255,0.08); }

.totals {
  display: grid;
  gap: var(--space-8);
  flex-shrink: 0;
}

.total-box {
  border: 1px solid var(--color-border);
  padding: var(--space-8);
  background: rgba(255,255,255,0.02);
}

.total-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 8px;
  margin-bottom: var(--space-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.total-value {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-text-primary);
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
  border: 1px dashed var(--color-border);
}

.placeholder-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
</style>
