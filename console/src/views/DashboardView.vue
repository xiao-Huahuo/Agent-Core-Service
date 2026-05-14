<!--
  观测面板 — macOS 终端风格占位页。
-->

<template>
  <div class="dashboard">
    <div class="placeholder-card">
      <span class="dollar">$</span>
      <span class="cmd">cat /var/log/agent/observability</span>
      <span class="comment">// 观测面板 — 即将上线</span>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.placeholder-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-8);
  font-family: var(--font-mono);
}

.dollar {
  font-size: var(--font-size-2xl);
  color: var(--color-green);
}

.cmd {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
}

.comment {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
}
</style>
