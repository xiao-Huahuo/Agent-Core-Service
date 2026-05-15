<!--
  TokenUsageCard — token 用量变化柱状图/曲线图展示卡片。
  使用说明: 放在记忆与知识面板上层右侧,宽+高。
-->

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">按时刻和模型的 token 用量变化</span>
      <span class="window-status">large + small</span>
    </div>
    <div class="macos-card-body card-placeholder">
      <span class="placeholder-text">$ 柱状图 / 曲线图，按时刻与模型拆分</span>
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
