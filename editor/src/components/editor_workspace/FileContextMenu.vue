<!--
  Shared knowledge file context menu.

  Usage:
  FileTreePanel and FileResourceManager render this component with the active
  node, paste availability, and menu position, then handle emitted actions.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useSettingsStore } from '@/stores/settings'
import type { KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'FileContextMenu' })

const settingsStore = useSettingsStore()
const favoritesStore = useFavoritesStore()

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
  showInGraph: []
  extractGraph: []
  askAgent: []
  htmlVisualize: []
  ingest: []
  toggleFavorite: []
  toggleIgnore: []
  delete: []
}>()

const menuRef = ref<HTMLElement | null>(null)
const isBatchSelection = computed(() => props.selectionCount > 1)
const hasTarget = computed(() => Boolean(props.node))
const canUseSingleOnlyAction = computed(() => !isBatchSelection.value && hasTarget.value)
const isTargetFavorite = computed(() => (
  props.node ? favoritesStore.isFavorite('knowledge_path', props.node.path, favoritesStore.activeLibraryId()) : false
))

defineExpose({
  getBoundingClientRect: () => menuRef.value?.getBoundingClientRect() ?? new DOMRect(),
})
</script>

<template>
  <div ref="menuRef" class="context-menu" :class="{ dark: settingsStore.isDark }" :style="menuStyle" @click.stop>
    <div class="context-submenu-item" :class="{ disabled: isBatchSelection }">
      <button type="button" :disabled="isBatchSelection"><IcIcon name="add" :size="15" /><span>新建</span><IcIcon name="chevron-right" :size="15" /></button>
      <div class="context-submenu">
        <button type="button" :disabled="isBatchSelection" @click="emit('createFile')"><IcIcon name="new-file" :size="15" /><span>新建文件</span><kbd>Ctrl+N</kbd></button>
        <button type="button" :disabled="isBatchSelection" @click="emit('createFolder')"><IcIcon name="new-folder" :size="15" /><span>新建文件夹</span><kbd>Ctrl+Shift+N</kbd></button>
      </div>
    </div>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('copy')"><IcIcon name="copy" :size="15" /><span>复制</span><kbd>Ctrl+C</kbd></button>
    <button type="button" :disabled="!node" @click="emit('cut')"><IcIcon name="cut" :size="15" /><span>剪切</span><kbd>Ctrl+X</kbd></button>
    <div class="context-submenu-item" :class="{ disabled: !canUseSingleOnlyAction }">
      <button type="button" :disabled="!canUseSingleOnlyAction"><IcIcon name="text-fields" :size="15" /><span>复制信息</span><IcIcon name="chevron-right" :size="15" /></button>
      <div class="context-submenu">
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
    <button type="button" :disabled="!canUseSingleOnlyAction" @click="emit('showInGraph')"><IcIcon name="graph" :size="15" /><span>在图谱中显示</span><kbd>Ctrl+G</kbd></button>
    <button type="button" :disabled="!node" @click="emit('extractGraph')">
      <IcIcon name="hub" :size="15" />
      <span>{{ node?.isDir ? '文件夹抽取图谱' : '文件抽取图谱' }}</span>
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
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('ingest')">
      <IcIcon name="ingest" :size="15" />
      <span>{{ node?.isDir ? '灌库文件夹' : '灌库文件' }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('toggleFavorite')">
      <IcIcon name="star" :size="15" />
      <span>{{ isTargetFavorite ? '取消收藏' : '收藏' }}</span>
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
  border-radius: var(--radius-sm);
  background: #ffffff;
  backdrop-filter: none;
  box-shadow: var(--shadow-lg);
}

.context-menu.dark {
  background: #151820;
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
  display: none;
  min-width: 260px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #ffffff;
  box-shadow: var(--shadow-lg);
}

.context-menu.dark .context-submenu {
  background: #151820;
}

.context-submenu-item:hover > .context-submenu,
.context-submenu-item:focus-within > .context-submenu {
  display: grid;
}

.context-submenu-item.disabled:hover > .context-submenu,
.context-submenu-item.disabled:focus-within > .context-submenu {
  display: none;
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
</style>
