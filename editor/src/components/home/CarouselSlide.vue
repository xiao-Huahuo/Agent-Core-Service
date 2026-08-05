<!--
  主页轮播单张幻灯片子组件。

  用法:
  由 CarouselBlock 在 v-for 中渲染。每张幻灯片独立使用 useHomeBlockImage,
  按块形状(block/rectangle)自动选背景图并定时概率切换(crossfade 淡入淡出),
  文字/图标按图片明暗动态取黑或白;compact 模式缩小标题/图标并隐藏胶囊。
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useHomeBlockImage } from '@/composable/useHomeBlockImage'
import type { WorkspaceMainView } from '@/types/knowledge'
import type { CarouselSlide } from './CarouselBlock.vue'

const props = defineProps<{
  /** 幻灯片数据。 */
  slide: CarouselSlide
  /** 紧凑模式: 标题/图标对齐导航块且不显示胶囊。 */
  compact?: boolean
}>()

const emit = defineEmits<{ open: [view: WorkspaceMainView] }>()

const rootRef = ref<HTMLElement | null>(null)
const { frontUrl, textTone } = useHomeBlockImage(props.slide.image ?? '', rootRef)
</script>

<template>
  <button
    ref="rootRef"
    class="carousel-slide"
    :class="{ compact }"
    :data-tone="textTone ?? undefined"
    type="button"
    :aria-label="`进入${slide.title}`"
    @click="emit('open', slide.target)"
  >
    <!-- 背景图单层渲染, key 变化时由 Transition 交叉淡入淡出 -->
    <Transition name="crossfade">
      <div
        v-if="frontUrl"
        :key="frontUrl"
        class="carousel-bg"
        :style='{ backgroundImage: `url("${frontUrl}")` }'
      />
    </Transition>
    <IcIcon :name="slide.icon" :size="compact ? 44 : 64" class="carousel-icon" aria-hidden="true" />
    <span class="carousel-title">{{ slide.title }}</span>
    <div class="carousel-sub-row">
      <span class="carousel-subtitle">{{ slide.subtitle }}</span>
    </div>
    <span v-if="!compact" class="carousel-hint">{{ slide.hint }} →</span>
  </button>
</template>

<style scoped>
.carousel-slide {
  position: relative;
  flex: 0 0 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-end;
  gap: var(--space-8);
  min-width: 0;
  padding: var(--space-32);
  border: 0;
  background-color: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  overflow: hidden;
  cursor: pointer;
}

/* 背景图层: 铺满幻灯片, 位于内容与悬停光效之下 */
.carousel-bg {
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

/* 文字动态对比: 依据背景图明暗决定深浅色系(由 useHomeBlockImage 的 data-tone 驱动) */
.carousel-slide[data-tone='dark'] {
  --home-title: #ffffff;
  --home-subtitle: rgba(255, 255, 255, 0.88);
  --home-icon: rgba(255, 255, 255, 0.92);
  --home-text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}

.carousel-slide[data-tone='light'] {
  --home-title: #171721;
  --home-subtitle: rgba(23, 23, 33, 0.74);
  --home-icon: rgba(23, 23, 33, 0.82);
  --home-text-shadow: 0 1px 2px rgba(255, 255, 255, 0.4);
}

.carousel-icon {
  position: absolute;
  top: 50%;
  right: var(--space-32);
  transform: translateY(-50%);
  opacity: 0.4;
  color: var(--home-icon, var(--color-text-secondary));
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}

.carousel-slide:hover .carousel-icon {
  opacity: 0.66;
  transform: translateY(-50%) scale(1.06);
}

.carousel-title,
.carousel-sub-row,
.carousel-hint,
.carousel-icon {
  text-shadow: var(--home-text-shadow, none);
}

.carousel-title,
.carousel-sub-row {
  position: relative;
  z-index: 1;
}

.carousel-title {
  max-width: min(70%, 720px);
  color: var(--home-title, var(--color-text));
  font-size: calc(1.9rem * var(--font-scale));
  font-weight: var(--font-weight-semibold);
  line-height: 1.15;
}

/* 第二行: 小字副标题 */
.carousel-sub-row {
  display: flex;
  align-items: center;
  max-width: min(70%, 720px);
}

.carousel-subtitle {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: calc(0.95rem * var(--font-scale));
  line-height: 1.5;
  color: var(--home-subtitle, var(--color-text-secondary));
}

/* 胶囊: 固定在右下角 */
.carousel-hint {
  position: absolute;
  right: var(--space-32);
  bottom: var(--space-24);
  z-index: 2;
  display: inline-flex;
  align-items: center;
  padding: var(--space-6) var(--space-16);
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 16%, transparent);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  transition: background var(--transition-fast);
}

.carousel-slide:hover .carousel-hint {
  background: color-mix(in srgb, var(--color-primary) 26%, transparent);
}

/* 紧凑模式: 标题/图标对齐导航块,不显示胶囊 */
.carousel-slide.compact {
  padding: var(--space-20);
}

.carousel-slide.compact .carousel-icon {
  top: var(--space-16);
  right: var(--space-16);
  transform: none;
  opacity: 0.38;
}

.carousel-slide.compact:hover .carousel-icon {
  opacity: 0.62;
  transform: scale(1.06);
}

.carousel-slide.compact .carousel-title {
  font-size: calc(1.05rem * var(--font-scale));
  line-height: 1.2;
}

.carousel-slide:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

@media (prefers-reduced-motion: reduce) {
  .carousel-slide,
  .carousel-bg,
  .carousel-icon,
  .carousel-hint {
    transition: none;
  }
}
</style>
