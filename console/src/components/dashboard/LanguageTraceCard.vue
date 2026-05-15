<!--
  LanguageTraceCard — 语言轨迹观测 ⇄ 上下文拼装切换卡片。
  使用说明: 放在 Agent 轨迹面板中栏,通过标题栏 tabs 切换子视图。
-->

<script setup>
import { ref } from 'vue'

const activeTab = ref('trace')
</script>

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <div class="titlebar-tabs">
        <button
          class="titlebar-tab"
          :class="{ active: activeTab === 'trace' }"
          @click="activeTab = 'trace'"
        >
          语言轨迹
        </button>
        <button
          class="titlebar-tab"
          :class="{ active: activeTab === 'context' }"
          @click="activeTab = 'context'"
        >
          上下文拼装
        </button>
      </div>
      <span class="window-status">{{ activeTab === 'trace' ? 'live' : '可读格式' }}</span>
    </div>
    <div class="macos-card-body card-placeholder">
      <span v-if="activeTab === 'trace'" class="placeholder-text">
        $ 大小模型输入输出日志，不同颜色区分
      </span>
      <span v-else class="placeholder-text">
        $ 可切换 JSON 格式与可读格式，来源颜色区分
      </span>
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

.titlebar-tabs {
  display: flex;
  align-items: center;
  gap: 1px;
  margin-left: var(--space-8);
  flex-shrink: 0;
}

.titlebar-tab {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.titlebar-tab:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.titlebar-tab.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.3);
  background: var(--color-accent-muted);
}

.card-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-24) var(--space-16);
}

.placeholder-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  text-align: center;
  line-height: var(--line-height-relaxed);
}
</style>
