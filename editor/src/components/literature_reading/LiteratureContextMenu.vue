<!--
  Literature reading context menu.

  Usage:
  LiteratureReadingView positions this menu for either a whole literature card
  or one expanded field and handles every emitted business action.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'

defineProps<{
  kind: 'row' | 'field'
  x: number
  y: number
}>()

defineEmits<{
  action: [name: string]
}>()
</script>

<template>
  <div class="literature-context ui-floating-menu-surface" :style="{ left: `${x}px`, top: `${y}px` }" role="menu" @click.stop>
    <template v-if="kind === 'row'">
      <button type="button" @click="$emit('action', 'new')"><IcIcon name="add" :size="15" /><span>新建</span></button>
      <button type="button" @click="$emit('action', 'add-field')"><IcIcon name="view-column" :size="15" /><span>新增字段</span></button>
      <button type="button" @click="$emit('action', 'duplicate')"><IcIcon name="copy" :size="15" /><span>复制</span></button>
      <div class="submenu-item">
        <button type="button"><IcIcon name="link" :size="15" /><span>复制路径</span><IcIcon name="chevron-right" :size="13" /></button>
        <div class="path-submenu ui-floating-submenu-surface">
          <button type="button" @click="$emit('action', 'copy-name')">复制文献名称</button>
          <button type="button" @click="$emit('action', 'copy-relative')">复制文献相对路径</button>
          <button type="button" @click="$emit('action', 'copy-absolute')">复制文献绝对路径</button>
        </div>
      </div>
      <button type="button" @click="$emit('action', 'rename')"><IcIcon name="edit" :size="15" /><span>重命名</span></button>
      <button type="button" @click="$emit('action', 'fill')"><IcIcon name="psychology" :size="15" /><span>智能填充</span></button>
      <button type="button" @click="$emit('action', 'reupload')"><IcIcon name="upload" :size="15" /><span>重新上传文献</span></button>
      <button type="button" @click="$emit('action', 'clear-invalid')"><IcIcon name="remove" :size="15" /><span>清空无效字段</span></button>
      <button type="button" @click="$emit('action', 'reveal')"><IcIcon name="folder-open" :size="15" /><span>在文件夹中显示</span></button>
      <button type="button" @click="$emit('action', 'open-default')"><IcIcon name="open-in-new" :size="15" /><span>用默认程序打开</span></button>
      <button type="button" @click="$emit('action', 'favorite')"><IcIcon name="star" :size="15" /><span>收藏</span></button>
      <button type="button" @click="$emit('action', 'privacy')"><IcIcon name="visibility-off" :size="15" /><span>隐私化</span></button>
      <button class="danger" type="button" @click="$emit('action', 'delete')"><IcIcon name="trash" :size="15" /><span>删除</span></button>
    </template>
    <template v-else>
      <button type="button" @click="$emit('action', 'fill-field')"><IcIcon name="psychology" :size="15" /><span>智能填充 / 重新填充</span></button>
      <button type="button" @click="$emit('action', 'clear-field')"><IcIcon name="remove" :size="15" /><span>清空</span></button>
      <button type="button" @click="$emit('action', 'add-field')"><IcIcon name="view-column" :size="15" /><span>新增字段</span></button>
    </template>
  </div>
</template>

<style scoped>
.literature-context,
.path-submenu {
  position: fixed;
  z-index: 100000;
  display: grid;
  min-width: 236px;
  padding: 6px;
}

.literature-context button,
.path-submenu button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  padding: 0 8px;
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  text-align: left;
}

.literature-context button:hover,
.path-submenu button:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.literature-context button.danger:hover {
  background: color-mix(in srgb, var(--color-danger) 12%, var(--color-canvas));
  color: var(--color-danger);
}

.submenu-item {
  position: relative;
}

.submenu-item > button {
  width: 100%;
}

.path-submenu {
  position: absolute;
  top: -6px;
  left: calc(100% + 8px);
  display: none;
  width: 236px;
}

.path-submenu button {
  grid-template-columns: minmax(0, 1fr);
}

.submenu-item:hover .path-submenu,
.submenu-item:focus-within .path-submenu {
  display: grid;
}
</style>
