<!--
  KnowledgeRecallCard — 知识库召回 ReRank 前/后对比卡片。
  使用说明: 放在记忆与知识面板下层中间,窄。
-->

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">知识库召回</span>
      <span class="window-status">ReRank 前</span>
    </div>
    <div class="macos-card-body card-placeholder">
      <span class="placeholder-text">$ 可切换 ReRank 前 / ReRank 后</span>
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
