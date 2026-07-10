<!--
  RagMetricsCard —— RAG 召回率、命中率、置信度展示卡片。
  可切换 donut(本轮) / line(全会话历史)。
  ECharts 渲染，弹性布局。
-->

<script setup>
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import { useObsData } from '@/composable/useObsData'

const obs = useObsData()
const chartMode = ref('donut')

const GREEN = '#6ee7b7'
const BLUE = '#4da6ff'
const ACCENT = '#d99178'
const BG_MUTED = 'rgba(255,255,255,0.06)'
const TXT_PRIMARY = '#e0e0e0'
const TXT_LABEL = '#777'
const BORDER = 'rgba(255,255,255,0.08)'
const metricConfigs = [
  { key: 'recall', label: 'recall', color: GREEN },
  { key: 'hitRate', label: 'hit rate', color: BLUE },
  { key: 'confidence', label: 'confidence', color: ACCENT },
]

/** 三个环形指标 */
const gaugeOption = (value, color) => ({
  backgroundColor: 'transparent',
  series: [
    {
      type: 'pie',
      radius: ['52%', '72%'],
      center: ['50%', '50%'],
      silent: true,
      emphasis: { disabled: true },
      label: { show: false },
      labelLine: { show: false },
      data: [
        { value, itemStyle: { color } },
        { value: Math.max(0, 100 - value), itemStyle: { color: BG_MUTED } },
      ],
    },
  ],
})

const donutItems = computed(() => {
  const m = obs.ragMetrics.value
  return metricConfigs.map((item) => ({
    ...item,
    value: m[item.key],
    option: gaugeOption(m[item.key], item.color),
  }))
})

/** 曲线图：会话级三率历史 */
const lineOption = computed(() => {
  const rows = obs.ragHistory.value
  return {
    backgroundColor: 'transparent',
    grid: { top: 12, right: 16, bottom: 24, left: 36 },
    xAxis: {
      type: 'category',
      data: rows.map((r) => `R${r.turn}`),
      axisLine: { lineStyle: { color: BORDER } },
      axisTick: { show: false },
      axisLabel: { color: TXT_LABEL, fontSize: 8 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: BORDER, type: 'dashed' } },
      axisLabel: { color: TXT_LABEL, fontSize: 8 },
    },
    series: [
      {
        name: 'recall',
        type: 'line',
        data: rows.map((r) => r.recall),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: BLUE, width: 1.5 },
        itemStyle: { color: BLUE },
      },
      {
        name: 'hit rate',
        type: 'line',
        data: rows.map((r) => r.hitRate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: GREEN, width: 1.5 },
        itemStyle: { color: GREEN },
      },
      {
        name: 'confidence',
        type: 'line',
        data: rows.map((r) => r.confidence),
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: ACCENT, width: 1.8 },
        itemStyle: { color: ACCENT },
      },
    ],
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
      <span class="window-filename">RAG 召回率 / 命中率 / 置信度</span>
      <span class="window-status">{{ chartMode === 'donut' ? '本轮' : '历史' }}</span>
    </div>

    <div class="card-body">
      <div class="chart-toolbar">
        <button class="chart-mode-btn" :class="{ active: chartMode === 'donut' }" @click="chartMode = 'donut'">饼图</button>
        <button class="chart-mode-btn" :class="{ active: chartMode === 'line' }" @click="chartMode = 'line'">曲线图</button>
      </div>

      <!-- 三个 donut -->
      <div v-if="chartMode === 'donut'" class="gauges-row">
        <div v-for="item in donutItems" :key="item.key" class="gauge-item">
          <div class="gauge-chart-wrap">
            <v-chart :option="item.option" autoresize class="gauge-chart" />
          </div>
          <div class="gauge-meta">
            <span class="gauge-value" :style="{ color: item.color }">{{ item.value }}%</span>
            <span class="gauge-label">{{ item.label }}</span>
          </div>
        </div>
      </div>

      <!-- 曲线图 -->
      <div v-else class="line-chart-wrap">
        <v-chart :option="lineOption" autoresize class="line-chart" />
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
.chart-mode-btn.active { color: var(--color-accent); border-color: rgba(217,145,120,0.3); background: var(--color-accent-muted); }

.gauges-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.gauge-item {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  align-items: stretch;
  justify-items: center;
  gap: var(--space-6);
  min-width: 0;
  min-height: 150px;
}

.gauge-chart-wrap {
  width: 100%;
  height: 100%;
}

.gauge-chart {
  width: 100%;
  height: 100%;
}

.gauge-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 0;
}

.gauge-value {
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1;
}

.gauge-label {
  font-family: var(--font-mono);
  font-size: 8px;
  line-height: 1.3;
  color: var(--color-text-tertiary);
  text-transform: lowercase;
}

.line-chart-wrap {
  flex: 1;
  min-height: 0;
}

.line-chart {
  width: 100%;
  height: 100%;
}

@media (max-width: 1180px) {
  .gauges-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .gauges-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-6);
  }

  .gauge-item {
    min-height: 112px;
    gap: var(--space-4);
  }

  .gauge-chart-wrap {
    width: 100%;
    max-width: 88px;
    justify-self: center;
  }

  .gauge-value {
    font-size: 12px;
  }

  .gauge-label {
    font-size: 7px;
  }
}
</style>
