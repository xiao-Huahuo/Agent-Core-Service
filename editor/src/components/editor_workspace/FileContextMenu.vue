<!--
  Shared knowledge file context menu.

  Usage:
  FileTreePanel and FileResourceManager render this component with the active
  node, paste availability, and menu position, then handle emitted actions.
-->
<script setup lang="ts">
import { ref } from 'vue'

import { useSettingsStore } from '@/stores/settings'
import type { KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'FileContextMenu' })

const settingsStore = useSettingsStore()

defineProps<{
  node: KnowledgeFileNode | null
  canPaste: boolean
  menuStyle: Record<string, string>
}>()

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
  ingest: []
  toggleIgnore: []
  delete: []
}>()

const menuRef = ref<HTMLElement | null>(null)

defineExpose({
  getBoundingClientRect: () => menuRef.value?.getBoundingClientRect() ?? new DOMRect(),
})
</script>

<template>
  <div ref="menuRef" class="context-menu" :class="{ dark: settingsStore.isDark }" :style="menuStyle" @click.stop>
    <button type="button" @click="emit('createFile')"><span>新建文件</span><kbd>Ctrl+N</kbd></button>
    <button type="button" @click="emit('createFolder')"><span>新建文件夹</span><kbd>Ctrl+Shift+N</kbd></button>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('copy')"><span>复制</span><kbd>Ctrl+C</kbd></button>
    <button type="button" :disabled="!node" @click="emit('cut')"><span>剪切</span><kbd>Ctrl+X</kbd></button>
    <button type="button" :disabled="!node" @click="emit('copyName')"><span>复制名称</span></button>
    <button type="button" :disabled="!node" @click="emit('copyAbsolutePath')"><span>复制绝对路径</span></button>
    <button type="button" :disabled="!node" @click="emit('copyRelativePath')"><span>复制相对路径</span></button>
    <hr class="context-separator" />
    <button type="button" :disabled="!canPaste" @click="emit('paste')"><span>粘贴</span><kbd>Ctrl+V</kbd></button>
    <button type="button" :disabled="!node" @click="emit('rename')"><span>重命名</span><kbd>Ctrl+M</kbd></button>
    <hr class="context-separator" />
    <button type="button" @click="emit('showInFolder')">
      <span>{{ node ? '在文件夹中显示' : '打开知识库根目录' }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('openDefault')"><span>用默认程序打开</span></button>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('showInGraph')"><span>在图谱中显示</span><kbd>Ctrl+G</kbd></button>
    <button type="button" :disabled="!node" @click="emit('extractGraph')">
      <span>{{ node?.isDir ? '文件夹抽取图谱' : '文件抽取图谱' }}</span>
    </button>
    <hr class="context-separator" />
    <button type="button" @click="emit('askAgent')"><span>询问 Agent</span></button>
    <hr class="context-separator" />
    <button type="button" :disabled="!node" @click="emit('ingest')">
      <span>{{ node?.isDir ? '灌库文件夹' : '灌库文件' }}</span>
    </button>
    <button type="button" :disabled="!node" @click="emit('toggleIgnore')">
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
      <span>删除</span><kbd>Ctrl+D</kbd>
    </button>
  </div>
</template>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 40;
  display: grid;
  min-width: 232px;
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
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-12);
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
