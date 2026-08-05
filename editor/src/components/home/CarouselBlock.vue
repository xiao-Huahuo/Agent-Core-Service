<!--
  主页轮播子组件。

  用法:
  GTAOL 风格主视觉轮播,占据主页最大区块。每张幻灯片为可点击入口,
  点击后通过 open 事件上抛跳转目标。默认自动播放,悬停或聚焦时暂停。
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import type { WorkspaceMainView } from '@/types/knowledge'

interface CarouselSlide {
  /** IcIcon 图标名。 */
  icon: string
  /** 幻灯片标题。 */
  title: string
  /** 幻灯片副标题。 */
  subtitle: string
  /** 底部提示文案。 */
  hint: string
  /** 点击后跳转的工作区视图。 */
  target: WorkspaceMainView
}

const props = defineProps<{ slides?: CarouselSlide[] }>()

const emit = defineEmits<{ open: [view: WorkspaceMainView] }>()

const DEFAULT_SLIDES: CarouselSlide[] = [
  {
    icon: 'psychology',
    title: 'Agent 智能体',
    subtitle: '与 AI 对话,让智能体协助你总结、整理与可视化知识库内容',
    hint: '开始对话',
    target: 'agent',
  },
  {
    icon: 'graph',
    title: '知识图谱',
    subtitle: '将文档抽取为实体与关系,一键洞察知识库的整体结构',
    hint: '查看图谱',
    target: 'graph',
  },
  {
    icon: 'book',
    title: '图书馆',
    subtitle: '浏览、收藏与管理你的知识库文档与文件夹',
    hint: '进入图书馆',
    target: 'library',
  },
  {
    icon: 'search',
    title: '全库搜索',
    subtitle: '全文检索与语义检索双通道,快速定位目标文档',
    hint: '开始搜索',
    target: 'search',
  },
  {
    icon: 'code',
    title: 'MD-HTML 可视化',
    subtitle: '让 AI 将文档重排为更精美的 HTML 可视化页面',
    hint: '去可视化',
    target: 'visualization',
  },
]

const slides = computed(() => props.slides ?? DEFAULT_SLIDES)
const activeIndex = ref(0)
const paused = ref(false)

const AUTOPLAY_MS = 5000
let timer: ReturnType<typeof setInterval> | null = null

function goTo(index: number) {
  activeIndex.value = (index + slides.value.length) % slides.value.length
}

function stopAutoplay() {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

function startAutoplay() {
  stopAutoplay()
  timer = setInterval(() => {
    if (!paused.value) {
      goTo(activeIndex.value + 1)
    }
  }, AUTOPLAY_MS)
}

onMounted(startAutoplay)
onBeforeUnmount(stopAutoplay)
</script>

<template>
  <div
    class="carousel-block"
    @mouseenter="paused = true"
    @mouseleave="paused = false"
    @focusin="paused = true"
    @focusout="paused = false"
  >
    <div
      class="carousel-track"
      :style="{ transform: `translateX(-${activeIndex * 100}%)` }"
    >
      <button
        v-for="(slide, index) in slides"
        :key="slide.target"
        class="carousel-slide"
        type="button"
        :aria-label="`进入${slide.title}`"
        @click="emit('open', slide.target)"
      >
        <span class="carousel-index">{{ String(index + 1).padStart(2, '0') }}</span>
        <IcIcon :name="slide.icon" :size="64" class="carousel-icon" aria-hidden="true" />
        <span class="carousel-title">{{ slide.title }}</span>
        <div class="carousel-sub-row">
          <span class="carousel-subtitle">{{ slide.subtitle }}</span>
          <span class="carousel-hint">{{ slide.hint }} →</span>
        </div>
      </button>
    </div>
    <div class="carousel-dots">
      <button
        v-for="(slide, index) in slides"
        :key="`dot-${slide.target}`"
        class="carousel-dot"
        :class="{ active: index === activeIndex }"
        type="button"
        :aria-label="`切换到第 ${index + 1} 张`"
        @click="goTo(index)"
      ></button>
    </div>
  </div>
</template>

<style scoped>
.carousel-block {
  position: relative;
  width: 100%;
  height: 100%;
  border: 1px solid var(--color-border);
  border-radius: 0;
  overflow: hidden;
  /* 小阴影 */
  box-shadow: var(--home-card-shadow);
  background: var(--color-surface);
  transition: border-color var(--transition-normal);
}

/* 悬停光效: 与导航块一致的柔和主题色(亮) / 白色(暗) */
.carousel-block::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  background: radial-gradient(120% 130% at 50% 0%, var(--home-hover-glow), transparent 68%);
  opacity: 0;
  transition: opacity var(--transition-normal);
  pointer-events: none;
}

.carousel-block:hover {
  border-color: var(--home-hover-border);
}

.carousel-block:hover::after {
  opacity: 1;
}

.carousel-track {
  display: flex;
  width: 100%;
  height: 100%;
  transition: transform 600ms cubic-bezier(0.22, 1, 0.36, 1);
}

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
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  overflow: hidden;
  cursor: pointer;
}

.carousel-index {
  position: absolute;
  top: var(--space-24);
  left: var(--space-32);
  font-family: var(--font-code);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  letter-spacing: 0.12em;
}

.carousel-icon {
  position: absolute;
  top: 50%;
  right: var(--space-32);
  transform: translateY(-50%);
  opacity: 0.4;
  color: var(--color-text-secondary);
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}

.carousel-slide:hover .carousel-icon {
  opacity: 0.66;
  transform: translateY(-50%) scale(1.06);
}

.carousel-title,
.carousel-sub-row {
  position: relative;
  z-index: 1;
}

.carousel-title {
  max-width: min(70%, 720px);
  font-size: calc(1.9rem * var(--font-scale));
  font-weight: var(--font-weight-semibold);
  line-height: 1.15;
}

/* 第二行: 小字副标题 + 右侧胶囊 */
.carousel-sub-row {
  display: flex;
  align-items: center;
  gap: var(--space-12);
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
  color: var(--color-text-secondary);
}

.carousel-hint {
  flex: 0 0 auto;
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

.carousel-dots {
  position: absolute;
  bottom: var(--space-16);
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-10);
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-surface) 70%, transparent);
  backdrop-filter: blur(6px);
}

.carousel-dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: var(--color-border-strong);
  transition: background var(--transition-fast), transform var(--transition-fast);
}

.carousel-dot.active {
  width: 20px;
  border-radius: 999px;
  background: var(--color-primary);
}

.carousel-slide:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.carousel-dot:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .carousel-block::after,
  .carousel-track,
  .carousel-icon,
  .carousel-hint {
    transition: none;
  }
}
</style>
