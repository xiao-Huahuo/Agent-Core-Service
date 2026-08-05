<!--
  主页导航分块子组件。

  用法:
  以图片分块卡片展示一个可点击入口,纯色底、直角、带小阴影,悬停有光效。
  点击后通过 open 事件将跳转目标上抛给主页处理。
  悬停光效: 亮色为柔和主题色,暗色为白色,由 --home-hover-glow 主题变量控制。
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import type { WorkspaceMainView } from '@/types/knowledge'

defineProps<{
  /** IcIcon 图标名。 */
  icon: string
  /** 区块标题。 */
  title: string
  /** 区块副标题。 */
  subtitle: string
  /** 点击后跳转的工作区视图。 */
  target: WorkspaceMainView
}>()

const emit = defineEmits<{ open: [view: WorkspaceMainView] }>()
</script>

<template>
  <button
    class="nav-block"
    type="button"
    :aria-label="`进入${title}`"
    @click="emit('open', target)"
  >
    <IcIcon :name="icon" :size="44" class="nav-block-icon" aria-hidden="true" />
    <div class="nav-block-copy">
      <span class="nav-block-title">{{ title }}</span>
      <span class="nav-block-subtitle">{{ subtitle }}</span>
    </div>
    <span class="nav-block-hint">进入 →</span>
  </button>
</template>

<style scoped>
.nav-block {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-end;
  gap: var(--space-6);
  width: 100%;
  height: 100%;
  padding: var(--space-20);
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  overflow: hidden;
  /* 小阴影 */
  box-shadow: var(--home-card-shadow);
  transition:
    border-color var(--transition-normal),
    transform var(--transition-normal),
    box-shadow var(--transition-normal);
}

/* 悬停光效: 柔和主题色(亮) / 白色(暗),以径向渐变叠加 */
.nav-block::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 130% at 50% 0%, var(--home-hover-glow), transparent 68%);
  opacity: 0;
  transition: opacity var(--transition-normal);
  pointer-events: none;
}

.nav-block:hover {
  border-color: var(--home-hover-border);
  transform: translateY(-1px);
  box-shadow: var(--home-card-shadow);
}

.nav-block:hover::after {
  opacity: 1;
}

.nav-block-icon {
  position: absolute;
  top: var(--space-16);
  right: var(--space-16);
  opacity: 0.38;
  color: var(--color-text-secondary);
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}

.nav-block:hover .nav-block-icon {
  opacity: 0.62;
  transform: scale(1.06);
}

.nav-block-copy {
  position: relative;
  z-index: 1;
}

/* 大字标题 + 小字副标题同一行展示 */
.nav-block-copy {
  display: flex;
  align-items: baseline;
  gap: var(--space-8);
  max-width: 100%;
}

.nav-block-title {
  flex: 0 0 auto;
  white-space: nowrap;
  font-size: calc(1.05rem * var(--font-scale));
  font-weight: var(--font-weight-semibold);
  line-height: 1.2;
}

.nav-block-subtitle {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: var(--font-size-xs);
  line-height: 1.4;
  color: var(--color-text-muted);
}

/* 「进入 →」悬浮时显示,绝对定位不占文档流,避免文字行下方留空隙 */
.nav-block-hint {
  position: absolute;
  right: var(--space-20);
  bottom: var(--space-20);
  z-index: 1;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  opacity: 0;
  transform: translateY(4px);
  transition:
    opacity var(--transition-normal),
    transform var(--transition-normal);
}

.nav-block:hover .nav-block-hint {
  opacity: 1;
  transform: translateY(0);
}

.nav-block:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .nav-block,
  .nav-block::after,
  .nav-block-icon,
  .nav-block-hint {
    transition: none;
  }
}
</style>
