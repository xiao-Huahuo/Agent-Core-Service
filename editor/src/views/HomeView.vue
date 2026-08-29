<!--
  主页页面组件。

  用法:
  以类似 GTAOL 主页的图片分块引导各个页面入口,最大区块为轮播。
  布局: 上半左 2/3 为轮播、右 1/3 上下切两块;下半左/中 1/3 各一块、
  右 1/3 上下切两块(上块切看板/浏览器),右下角为剩余工具入口轮播。
  块直角、带小阴影、有间隙、悬停光效,点击跳转到对应视图。桌面 3 列,平板 2 列,窄屏纵向堆叠。
-->
<script setup lang="ts">
import CarouselBlock, { type CarouselSlide } from '@/components/home/CarouselBlock.vue'
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
  /** 背景图对应的块目录名(assets/images/home/<名>)。 */
  image?: string
}

/** 左上主轮播: 六种知识形态入口。 */
const knowledgeSlides: CarouselSlide[] = [
  {
    icon: 'folder-open',
    title: '文件资源管理器',
    subtitle: '浏览与管理知识库文件',
    hint: '管理文件',
    target: 'resources',
    image: 'files',
    accent: 'var(--color-search-files)',
  },
  {
    icon: 'book',
    title: '图书馆',
    subtitle: '管理图书与集锦',
    hint: '进入图书馆',
    target: 'library',
    image: 'library',
    accent: 'var(--color-search-library)',
  },
  {
    icon: 'grid-view',
    title: '组件库',
    subtitle: '收藏与复用交互组件',
    hint: '浏览组件',
    target: 'component-library',
    image: 'components-vault',
    accent: 'var(--color-search-components)',
  },
  {
    icon: 'shield',
    title: '密码库',
    subtitle: '集中管理私密凭据',
    hint: '打开密码库',
    target: 'vault',
    image: 'secret-vault',
    accent: 'var(--color-library-vault)',
  },
  {
    icon: 'table-chart',
    title: '智能表格',
    subtitle: '结构化整理与批量比较',
    hint: '打开表格',
    target: 'forms',
    image: 'intelligent-forms',
    accent: 'var(--color-library-forms)',
  },
  {
    icon: 'document',
    title: '文献阅读',
    subtitle: '逐篇阅读与编辑科研文献',
    hint: '阅读文献',
    target: 'literature-reading',
    image: 'literature-reading',
    accent: 'var(--color-search-literature)',
  },
]

/** 上半右侧上下两块: Agent 与任务队列。 */
const upperTiles: HomeTile[] = [
  {
    area: 'a',
    icon: 'psychology',
    title: 'Agent 智能体',
    subtitle: '与 AI 协作整理知识',
    target: 'agent',
    image: 'agent',
  },
  {
    area: 'b',
    icon: 'checklist',
    title: '任务队列',
    subtitle: '并行调度独立 Agent 任务',
    target: 'agent-queue',
    image: 'mission-queue',
  },
]

/** 下半三列: 左全库联合搜索、中知识图谱。 */
const lowerTiles: HomeTile[] = [
  {
    area: 'c',
    icon: 'search',
    title: '全库联合搜索',
    subtitle: '统一检索文件、图书、组件与文献',
    target: 'search',
    image: 'search',
  },
  {
    area: 'd',
    icon: 'graph',
    title: '知识图谱',
    subtitle: '全局关系可视化',
    target: 'graph',
    image: 'graph',
  },
]

/** 右下角轮播: 页面其余位置尚未展示的有图入口。 */
const toolSlides: CarouselSlide[] = [
  {
    icon: 'bug',
    title: 'Debug',
    subtitle: '调试工具与运行日志',
    hint: '进入调试',
    target: 'debug',
    image: 'debug',
  },
  {
    icon: 'code',
    title: 'MD-HTML',
    subtitle: '文档可视化预览',
    hint: '去可视化',
    target: 'visualization',
    image: 'md-html',
  },
  {
    icon: 'settings',
    title: '设置',
    subtitle: '偏好与应用配置',
    hint: '打开设置',
    target: 'settings',
    image: 'settings',
  },
  {
    icon: 'auto-awesome',
    title: 'Skills',
    subtitle: '技能目录与编排',
    hint: '管理技能',
    target: 'skills',
    image: 'skills',
  },
]

function openView(view: WorkspaceMainView) {
  if (view === 'skills') {
    localStorage.setItem('agent_editor_settings_active_tab', 'skills')
    workspaceStore.setMainView('settings')
    return
  }
  workspaceStore.setMainView(view)
}
</script>

<template>
  <div class="home-view">
    <CarouselBlock class="home-carousel" :slides="knowledgeSlides" @open="openView" />
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
    <!-- e 区水平切割: 左看板、右浏览器。 -->
    <div class="tile-split" :style="{ gridArea: 'e' }">
      <NavBlock
        icon="dashboard"
        title="看板"
        subtitle="时间与用量观测"
        target="dashboard"
        image="visualization"
        @open="openView"
      />
      <NavBlock
        icon="language"
        title="浏览器"
        subtitle="内置网页浏览与资料查阅"
        target="browser"
        image="browser"
        @open="openView"
      />
    </div>
    <!-- f 区: 右下角轮播,展示其余有图入口。 -->
    <CarouselBlock
      class="home-tile-carousel"
      :style="{ gridArea: 'f' }"
      :slides="toolSlides"
      compact
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

/* e 区: 水平切割为两块,子块均分宽度、中间保留间隙 */
.tile-split {
  display: flex;
  gap: var(--space-12);
  min-height: 0;
}

.tile-split :deep(.nav-block) {
  flex: 1 1 0;
  min-width: 0;
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
