<!--
  Shared knowledge file context menu.

  Usage:
  FileTreePanel and FileResourceManager render this component with the active
  node, paste availability, and menu position, then handle emitted actions.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useSubmenuIntent } from '@/components/editor_workspace/submenuIntent'
import { useFavoritesStore } from '@/stores/favorites'
import { usePrivacyStore } from '@/stores/privacy'
import { useSettingsStore } from '@/stores/settings'
import type { KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'FileContextMenu' })

const settingsStore = useSettingsStore()
const favoritesStore = useFavoritesStore()
const privacyStore = usePrivacyStore()

const props = withDefaults(defineProps<{
  node: KnowledgeFileNode | null
  canPaste: boolean
  menuStyle: Record<string, string>
  selectionCount?: number
}>(), {
  selectionCount: 0,
})

const emit = defineEmits<{
  createFile: []
  createFolder: []
  copy: []
  cut: []
  copyName: []
  copyAbsolutePath: []
  copyRelativePath: []
  paste: []
  rename: []
  showInFolder: []
  openDefault: []
  extractGraph: []
  askAgent: []
  htmlVisualize: []
  ingest: []
  toggleFavorite: []
  togglePrivacy: []
  toggleIgnore: []
  delete: []
}>()

const menuRef = ref<HTMLElement | null>(null)
const activeSubmenu = ref('')
const submenuRefs: Record<string, HTMLElement | null> = {}
const {
  openSubmenu,
  keepSubmenuOpen,
  scheduleSubmenuClose,
} = useSubmenuIntent(activeSubmenu)
const isBatchSelection = computed(() => props.selectionCount > 1)
const hasTarget = computed(() => Boolean(props.node))
const canUseSingleOnlyAction = computed(() => !isBatchSelection.value && hasTarget.value)
const isTargetFavorite = computed(() => (
  props.node ? favoritesStore.isFavorite('knowledge_path', props.node.path, favoritesStore.activeLibraryId()) : false
))
const isTargetPrivate = computed(() => (
  props.node ? privacyStore.isPrivate('knowledge_path', props.node.path, privacyStore.activeLibraryId()) : false
))
const ingestionActionLabel = computed(() => {
  if (props.node?.isDir) return '灌库文件夹'
  const prefix = props.node?.indexStatus === 'indexed' ? '重新灌库' : '灌库'
  return `${prefix}文件`
})
const graphActionLabel = computed(() => {
  if (props.node?.isDir) return '文件夹抽取图谱'
  const prefix = props.node?.graphStatus === 'graphed' ? '重新抽取' : '抽取'
  return `${prefix}图谱`
})

function setSubmenuRef(key: string, element: unknown) {
  submenuRefs[key] = element instanceof HTMLElement ? element : null
}

function handleSubmenuLeave(key: string, event: MouseEvent) {
  const parent = event.currentTarget
  if (parent instanceof HTMLElement) {
    scheduleSubmenuClose(key, event, parent, submenuRefs[key] ?? null)
  }
}

defineExpose({
  getBoundingClientRect: () => menuRef.value?.getBoundingClientRect() ?? new DOMRect(),
})
</script>

<template>
  <div ref="menuRef" class="context-menu" :class="{ dark: settingsStore.isDark }" :style="menuStyle" @click.stop>
    <div
      class="context-submenu-item"
      :class="{ active: activeSubmenu === 'create', disabled: isBatchSelection }"
      @mouseenter="!isBatchSelection && openSubmenu('create')"
      @mouseleave="handleSubmenuLeave('create', $event)"
    >
      <button type="button" :disabled="isBatchSelection"><IcIcon name="add" :size="15" /><span>新建</span><IcIcon name="chevron-right" :size="15" /></button>
      <div
        v-show="activeSubmenu === 'create' && !isBatchSelection"
        :ref="(element) => setSubmenuRef('create', element)"
        class="context-submenu"
        @mouseenter="keepSubmenuOpen"
        @mouseleave="handleSubmenuLeave('create', $event)"
      >
        <button type="button" :disabled="isBatchSelection" @click="emit('createFile')"><IcIcon name="new-file" :size="15" /><span>新建文件</span><kbd>Ctrl+N</kbd></button>
        <button type="button" :disabled="isBatchSelection" @click="emit('createFolder')"><IcIcon name="new-folder" :size="15" /><span>新建文件夹</span><kbd>Ctrl+Shift+N</kbd></button>
      </div>
    </div>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('copy')"><IcIcon name="copy" :size="15" /><span>复制</span><kbd>Ctrl+C</kbd></button>
    <button type="button" :disabled="!node" @click="emit('cut')"><IcIcon name="cut" :size="15" /><span>剪切</span><kbd>Ctrl+X</kbd></button>
    <div
      class="context-submenu-item"
      :class="{ active: activeSubmenu === 'copy-info', disabled: !canUseSingleOnlyAction }"
      @mouseenter="canUseSingleOnlyAction && openSubmenu('copy-info')"
      @mouseleave="handleSubmenuLeave('copy-info', $event)"
    >
      <button type="button" :disabled="!canUseSingleOnlyAction"><IcIcon name="text-fields" :size="15" /><span>复制信息</span><IcIcon name="chevron-right" :size="15" /></button>
      <div
        v-show="activeSubmenu === 'copy-info' && canUseSingleOnlyAction"
        :ref="(element) => setSubmenuRef('copy-info', element)"
        class="context-submenu"
        @mouseenter="keepSubmenuOpen"
        @mouseleave="handleSubmenuLeave('copy-info', $event)"
      >
        <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('copyName')"><IcIcon name="text-fields" :size="15" /><span>复制名称</span></button>
        <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('copyAbsolutePath')"><IcIcon name="link" :size="15" /><span>复制绝对路径</span></button>
        <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('copyRelativePath')"><IcIcon name="arrow-right" :size="15" /><span>复制相对路径</span></button>
      </div>
    </div>
    <hr class="context-separator" />
    <button type="button" :disabled="!canPaste" @click="emit('paste')"><IcIcon name="paste" :size="15" /><span>粘贴</span><kbd>Ctrl+V</kbd></button>
    <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('rename')"><IcIcon name="edit" :size="15" /><span>重命名</span><kbd>Ctrl+M</kbd></button>
    <hr class="context-separator" />
    <button type="button" @click="emit('showInFolder')">
      <IcIcon name="folder-open" :size="15" />
      <span>{{ node ? '在文件夹中显示' : '打开知识库根目录' }}</span>
    </button>
    <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('openDefault')"><IcIcon name="open-in-new" :size="15" /><span>用默认程序打开</span></button>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('ingest')">
      <IcIcon name="ingest" :size="15" />
      <span>{{ ingestionActionLabel }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('extractGraph')">
      <IcIcon name="hub" :size="15" />
      <span>{{ graphActionLabel }}</span>
    </button>
    <hr class="context-separator" />
    <button
      type="button"
      data-action="html-visualize"
      :disabled="!canUseSingleOnlyAction || node?.isDir"
      @click="emit('htmlVisualize')"
    >
      <IcIcon name="code" :size="15" />
      <span>HTML可视化</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('toggleFavorite')">
      <IcIcon name="star" :size="15" />
      <span>{{ isTargetFavorite ? '取消收藏' : '收藏' }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('togglePrivacy')">
      <IcIcon name="visibility-off" :size="15" />
      <span>{{ isTargetPrivate ? '取消隐私化' : '隐私化' }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('toggleIgnore')">
      <IcIcon name="block" :size="15" />
      <span>
        {{
          node?.indexStatus === 'ignored'
            ? (node?.isDir ? '取消屏蔽文件夹' : '取消屏蔽文件')
            : (node?.isDir ? '屏蔽文件夹' : '屏蔽文件')
        }}
      </span>
    </button>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" class="danger" @click="emit('delete')">
      <IcIcon name="trash" :size="15" /><span>删除</span><kbd>Ctrl+D</kbd>
    </button>
  </div>
</template>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 40;
  display: grid;
  min-width: 280px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  backdrop-filter: none;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);
  transform-origin: top left;
  animation: context-menu-in 160ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.context-menu button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  column-gap: var(--space-10);
  min-height: 30px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  text-align: left;
}

.context-menu span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-menu kbd {
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.context-menu button:hover:not(:disabled) {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.context-menu button:disabled {
  cursor: default;
  opacity: 0.45;
}

.context-submenu-item {
  position: relative;
}

.context-submenu-item > button {
  width: 100%;
}

.context-submenu {
  position: absolute;
  top: calc(-1 * var(--space-6));
  left: calc(100% + var(--space-8));
  z-index: 1;
  display: grid;
  min-width: 260px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);
  transform-origin: top left;
  animation: context-submenu-in 150ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.context-submenu-item.active > button {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.context-separator {
  width: 100%;
  margin: var(--space-6) 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.context-menu .danger {
  color: var(--color-danger);
}

@keyframes context-menu-in {
  from { opacity: 0; transform: translateY(-4px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes context-submenu-in {
  from { opacity: 0; transform: translateX(-6px) scale(0.96); }
  to { opacity: 1; transform: translateX(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .context-menu,
  .context-submenu {
    animation-name: context-menu-fade;
    animation-duration: 120ms;
  }
}

@keyframes context-menu-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
