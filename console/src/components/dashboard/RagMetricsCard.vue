<!--
  RagMetricsCard — RAG 召回率 / 命中率 / 置信度展示卡片。
  使用说明: 放在记忆与知识面板上层左侧,窄+矮。
-->

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">RAG 召回率 / 命中率 / 置信度</span>
      <span class="window-status">本轮</span>
    </div>
    <div class="macos-card-body card-placeholder">
      <span class="placeholder-text">$ 饼图(本轮对话) / 曲线图(全会话历史)</span>
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
