<!--
  Shared editor-sidebar close control.

  Usage:
  EditorPane and non-file search result editors render this exact control in
  their upper-right toolbar so close behavior and visuals stay identical.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'EditorSidebarCloseButton' })

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <button class="sidebar-close-button" type="button" title="关闭编辑区侧边栏" aria-label="关闭编辑区侧边栏" @click="emit('close')">
    <IcIcon name="close" :size="15" />
  </button>
</template>

<style scoped>
.sidebar-close-button {
  display: inline-grid;
  width: 24px;
  height: 24px;
  place-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.sidebar-close-button:hover { color: var(--color-text); }
</style>
