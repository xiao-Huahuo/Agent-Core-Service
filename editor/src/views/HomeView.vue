<!--
  主页页面组件。

  用法:
  以类似 GTAOL 主页的图片分块引导各个页面入口,最大区块为轮播。
  布局: 上半左 2/3 为轮播、右 1/3 上下切两块;下半左/中 1/3 各一块、
  右 1/3 上下切两块。块直角、带小阴影、有间隙、悬停光效,点击跳转到对应视图。
  桌面为 3 列网格,平板 2 列,窄屏纵向堆叠。
-->
<script setup lang="ts">
import CarouselBlock from '@/components/home/CarouselBlock.vue'
import NavBlock from '@/components/home/NavBlock.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { WorkspaceMainView } from '@/types/knowledge'

const workspaceStore = useWorkspaceStore()

interface HomeTile {
  /** CSS grid-area 名称。 */
  area: string
  /** IcIcon 图标名。 */
  icon: string
  /** 区块标题。 */
  title: string
  /** 区块副标题。 */
  subtitle: string
  /** 点击后跳转的工作区视图。 */
  target: WorkspaceMainView
}

/** 上半右侧上下两块: Agent 与知识图谱。 */
const upperTiles: HomeTile[] = [
  {
    area: 'a',
    icon: 'psychology',
    title: 'Agent 智能体',
    subtitle: '与 AI 协作整理知识',
    target: 'agent',
  },
  {
    area: 'b',
    icon: 'graph',
    title: '知识图谱',
    subtitle: '全局关系可视化',
    target: 'graph',
  },
]

/** 下半三列: 左图书馆、中搜索、右 MD-HTML 与看板。 */
const lowerTiles: HomeTile[] = [
  {
    area: 'c',
    icon: 'book',
    title: '图书馆',
    subtitle: '浏览与管理知识库',
    target: 'library',
  },
  {
    area: 'd',
    icon: 'search',
    title: '搜索',
    subtitle: '全文与语义检索',
    target: 'search',
  },
  {
    area: 'e',
    icon: 'code',
    title: 'MD-HTML',
    subtitle: '文档可视化预览',
    target: 'visualization',
  },
  {
    area: 'f',
    icon: 'dashboard',
    title: '看板',
    subtitle: '时间与用量观测',
    target: 'dashboard',
  },
]

function openView(view: WorkspaceMainView) {
  workspaceStore.setMainView(view)
}
</script>

<template>
  <div class="home-view">
    <CarouselBlock class="home-carousel" @open="openView" />
    <NavBlock
      v-for="tile in upperTiles"
      :key="tile.target"
      :style="{ gridArea: tile.area }"
      v-bind="tile"
      @open="openView"
    />
    <NavBlock
      v-for="tile in lowerTiles"
      :key="tile.target"
      :style="{ gridArea: tile.area }"
      v-bind="tile"
      @open="openView"
    />
  </div>
</template>

<style scoped>
.home-view {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  /* 上半占两行,下半占两行,每行最小高度保证小窗下仍可用 */
  grid-template-rows: repeat(4, minmax(124px, 1fr));
  grid-template-areas:
    'carousel carousel a'
    'carousel carousel b'
    'c d e'
    'c d f';
  gap: var(--space-12);
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: var(--space-16);
  overflow: auto;
}

.home-carousel {
  grid-area: carousel;
  min-height: 0;
}

/* 平板: 两列,轮播占满整行 */
@media (max-width: 1024px) {
  .home-view {
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(4, minmax(150px, 1fr));
    grid-template-areas:
      'carousel carousel'
      'a b'
      'c d'
      'e f';
  }
}

/* 窄屏: 单列纵向堆叠,轮播固定较高 */
@media (max-width: 640px) {
  .home-view {
    grid-template-columns: 1fr;
    grid-template-rows: 240px repeat(6, 148px);
    grid-template-areas:
      'carousel'
      'a'
      'b'
      'c'
      'd'
      'e'
      'f';
  }
}
</style>
