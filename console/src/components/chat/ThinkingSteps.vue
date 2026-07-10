<!--
  思考步骤展示组件。

  接收 trace 数组,将每个节点的思考过程渲染为可折叠的步骤卡片。
  默认折叠,显示"> 思考中...";点击展开后展示各节点步骤,
  工具调用步骤可再点击查看详细参数和返回结果。
  新步骤追加时带滑入动画。
-->

<script setup>
import { ref } from 'vue'

const props = defineProps({
  traces: { type: Array, default: () => [] },
  isStreaming: { type: Boolean, default: false },
  defaultExpanded: { type: Boolean, default: false },
})

const emit = defineEmits(['collapse'])

const isExpanded = ref(props.defaultExpanded)

const stepExpanded = ref({})

function togglePanel() {
  if (isExpanded.value) {
    emit('collapse')
  } else {
    isExpanded.value = true
  }
}

function toggleStep(index) {
  stepExpanded.value[index] = !stepExpanded.value[index]
}

function nodeColor(node) {
  const map = {
    planner: 'var(--color-sky)',
    agent: 'var(--color-accent)',
    action: 'var(--color-blue)',
    observation: 'var(--color-green)',
    compress: 'var(--color-text-tertiary)',
    safety_input: 'var(--color-error)',
    safety_output: 'var(--color-error)',
  }
  return map[node] || 'var(--color-text-tertiary)'
}

/** 为每个 trace 生成稳定的 key: node + event + idx */
function traceKey(trace, idx) {
  return `${trace.node}-${trace.event}-${idx}`
}
</script>

<template>
  <div v-if="traces.length > 0" class="thinking-panel">
    <!-- 折叠栏 -->
    <div class="collapsed-bar" @click="togglePanel">
      <span class="bar-chevron" :class="{ expanded: isExpanded }">></span>
      <span v-if="!isExpanded && isStreaming" class="bar-text">思考中...</span>
      <span v-else-if="!isExpanded && !isStreaming" class="bar-text">思考完成</span>
      <span v-else class="bar-text">思考过程 ({{ traces.length }} 步)</span>
    </div>

    <!-- 展开的步骤列表: 带过渡动画 -->
    <Transition name="steps">
      <div v-if="isExpanded" class="thinking-steps">
        <div
          v-for="(trace, idx) in traces"
          :key="traceKey(trace, idx)"
          class="step-item"
          :class="{ 'is-tool': trace.event === 'tool_call_end', 'step-new': idx === traces.length - 1 && traces.length > 1 }"
        >
          <div class="step-header" @click="toggleStep(idx)">
            <span class="step-chevron" :class="{ expanded: stepExpanded[idx] }">></span>
            <span class="step-node" :style="{ color: nodeColor(trace.node) }">
              [{{ trace.node }}]
            </span>
            <span class="step-summary">{{ trace.human_readable || trace.event }}</span>
            <span v-if="trace.tool_name" class="step-tool-tag">{{ trace.tool_name }}</span>
          </div>

          <Transition name="detail">
            <div v-if="stepExpanded[idx] && (trace.tool_args_summary || trace.result_summary)" class="step-detail">
              <div v-if="trace.tool_args_summary" class="detail-block">
                <span class="detail-label">参数:</span>
                <pre class="detail-value">{{ trace.tool_args_summary }}</pre>
              </div>
              <div v-if="trace.result_summary" class="detail-block">
                <span class="detail-label">返回:</span>
                <pre class="detail-value">{{ trace.result_summary }}</pre>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ========== 面板 ========== */
.thinking-panel {
  margin-bottom: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* ========== 折叠栏 ========== */
.collapsed-bar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-8) var(--space-10);
  cursor: pointer;
  user-select: none;
  font-family: var(--font-mono);
  transition: background var(--transition-fast);
}

.collapsed-bar:hover {
  background: rgba(255, 255, 255, 0.03);
}

.bar-chevron {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  transition: transform 0.25s ease;
  display: inline-block;
}

.bar-chevron.expanded {
  transform: rotate(90deg);
}

.bar-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  transition: color var(--transition-fast);
}

/* ========== 面板展开/折叠过渡 ========== */
.steps-enter-active {
  transition: max-height 0.35s ease, opacity 0.3s ease;
  overflow: hidden;
}

.steps-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  overflow: hidden;
}

.steps-enter-from {
  max-height: 0;
  opacity: 0;
}

.steps-leave-to {
  max-height: 0;
  opacity: 0;
}

.steps-enter-to,
.steps-leave-from {
  max-height: 2000px;
  opacity: 1;
}

/* ========== 步骤列表 ========== */
.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid var(--color-border-light);
}

.step-item {
  background: rgba(255, 255, 255, 0.01);
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--transition-fast);
}

.step-item:last-child {
  border-bottom: none;
}

.step-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

/* 最新步骤入场动画 */
.step-new {
  animation: step-slide-in 0.4s ease-out;
}

@keyframes step-slide-in {
  from {
    opacity: 0;
    transform: translateY(-8px);
    max-height: 0;
  }
  to {
    opacity: 1;
    transform: translateY(0);
    max-height: 100px;
  }
}

/* ========== 步骤头部 ========== */
.step-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-6);
  padding: var(--space-8) var(--space-10);
  cursor: pointer;
  user-select: none;
  min-width: 0;
}

.step-chevron {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  transition: transform 0.2s ease;
  display: inline-block;
}

.step-chevron.expanded {
  transform: rotate(90deg);
}

.step-node {
  font-family: var(--font-mono);
  font-size: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  opacity: 0.7;
}

.step-summary {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
  flex: 1;
}

.step-tool-tag {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--color-blue);
  background: rgba(48, 128, 255, 0.1);
  padding: 1px var(--space-4);
  flex-shrink: 0;
}

/* ========== 工具详情折叠过渡 ========== */
.detail-enter-active {
  transition: max-height 0.3s ease, opacity 0.25s ease;
  overflow: hidden;
}

.detail-leave-active {
  transition: max-height 0.2s ease, opacity 0.15s ease;
  overflow: hidden;
}

.detail-enter-from,
.detail-leave-to {
  max-height: 0;
  opacity: 0;
}

.detail-enter-to,
.detail-leave-from {
  max-height: 600px;
  opacity: 1;
}

/* ========== 详情内容 ========== */
.step-detail {
  padding: var(--space-8) var(--space-10) var(--space-10) var(--space-32);
  border-top: 1px solid var(--color-border-light);
  background: rgba(0, 0, 0, 0.1);
}

.detail-block {
  margin-bottom: var(--space-6);
}

.detail-block:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
  margin-bottom: var(--space-4);
}

.detail-value {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  line-height: var(--line-height-relaxed);
  margin: 0;
  padding: var(--space-6) var(--space-8);
  background: rgba(0, 0, 0, 0.15);
  max-height: 160px;
  overflow-y: auto;
}
</style>
