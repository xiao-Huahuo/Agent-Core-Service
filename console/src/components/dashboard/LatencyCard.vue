<!--
  LatencyCard — 每次 message 思考时间耗时折线图卡片。
  使用说明: 放在记忆与知识面板下层右侧,纵贯下层。
-->

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">每次 message 思考时间耗时</span>
      <span class="window-status">折线图</span>
    </div>
    <div class="macos-card-body card-placeholder">
      <span class="placeholder-text">$ 点击耗时放大并划分为每个步骤的耗时占比</span>
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
