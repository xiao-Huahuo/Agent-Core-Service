<!--
  主页导航分块子组件。

  用法:
  以图片分块卡片展示一个可点击入口, 纯色底、直角、带小阴影, 悬停有光效。
  背景图按块形状(block/rectangle)自动选池并定时概率切换, 切换为交叉淡入淡出;
  文字/图标颜色按图片明暗动态取黑或白(无图时用默认主题色)。
  点击后通过 open 事件将跳转目标上抛给主页处理。
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useHomeBlockImage } from '@/composable/useHomeBlockImage'
import type { WorkspaceMainView } from '@/types/knowledge'

const props = defineProps<{
  /** IcIcon 图标名。 */
  icon: string
  /** 区块标题。 */
  title: string
  /** 区块副标题。 */
  subtitle: string
  /** 点击后跳转的工作区视图。 */
  target: WorkspaceMainView
  /** 背景图对应的块目录名(assets/images/home/<名>), 缺省则纯色底。 */
  image?: string
}>()

const emit = defineEmits<{ open: [view: WorkspaceMainView] }>()

const rootRef = ref<HTMLElement | null>(null)
const { frontUrl, textTone } = useHomeBlockImage(props.image ?? '', rootRef)
</script>

<template>
  <button
    ref="rootRef"
    class="nav-block"
    :data-tone="textTone ?? undefined"
    type="button"
    :aria-label="`进入${title}`"
    @click="emit('open', target)"
  >
    <!-- 背景图单层渲染, key 变化时由 Transition 交叉淡入淡出 -->
    <Transition name="crossfade">
      <div
        v-if="frontUrl"
        :key="frontUrl"
        class="nav-bg"
        :style='{ backgroundImage: `url("${frontUrl}")` }'
      />
    </Transition>
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
  background-color: var(--color-surface);
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

/* 背景图层: 铺满容器, 位于内容与悬停光效之下 */
.nav-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

/* 背景图切换交叉淡入淡出 */
.crossfade-enter-active,
.crossfade-leave-active {
  transition: opacity 500ms ease;
}

.crossfade-enter-from,
.crossfade-leave-to {
  opacity: 0;
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

/* 文字动态对比: 依据背景图明暗决定深浅色系(由 useHomeBlockImage 的 data-tone 驱动) */
.nav-block[data-tone='dark'] {
  --home-title: #ffffff;
  --home-subtitle: rgba(255, 255, 255, 0.88);
  --home-icon: rgba(255, 255, 255, 0.92);
  --home-icon-opacity: 0.55;
  --home-text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}

.nav-block[data-tone='light'] {
  --home-title: #171721;
  --home-subtitle: rgba(23, 23, 33, 0.74);
  --home-icon: rgba(23, 23, 33, 0.82);
  --home-icon-opacity: 0.55;
  --home-text-shadow: 0 1px 2px rgba(255, 255, 255, 0.4);
}

.nav-block-icon {
  position: absolute;
  top: var(--space-16);
  right: var(--space-16);
  opacity: var(--home-icon-opacity, 0.38);
  color: var(--home-icon, var(--color-text-secondary));
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

.nav-block-title,
.nav-block-subtitle,
.nav-block-hint,
.nav-block-icon {
  text-shadow: var(--home-text-shadow, none);
}

.nav-block-title {
  flex: 0 0 auto;
  white-space: nowrap;
  color: var(--home-title, var(--color-text));
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
  color: var(--home-subtitle, var(--color-text-muted));
}

/* 「进入 →」悬浮时显示,绝对定位不占文档流,避免文字行下方留空隙 */
.nav-block-hint {
  position: absolute;
  right: var(--space-20);
  bottom: var(--space-20);
  z-index: 1;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--home-title, var(--color-text-secondary));
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
  .nav-bg,
  .nav-block-icon,
  .nav-block-hint {
    transition: none;
  }
}
</style>
