<!--
  Shared duplicate-file conflict dialog.

  Usage:
  Rendered by the file tree or resource manager that initiated an import/paste
  operation so the duplicate strategy prompt appears in the active surface.
-->
<script setup lang="ts">
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
</script>

<template>
  <div class="conflict-backdrop" @click.self="workspaceStore.cancelConflict()">
    <section class="conflict-dialog" role="dialog" aria-modal="true" aria-labelledby="conflict-title">
      <h2 id="conflict-title">发现重复文件</h2>
      <p>目标文件夹已存在以下名称，请选择处理方式。</p>
      <ul class="conflict-file-list">
        <li v-for="name in workspaceStore.conflictDialog.conflictingNames" :key="name">{{ name }}</li>
      </ul>
      <div class="conflict-actions">
        <button type="button" @click="workspaceStore.resolveConflict('overwrite')">覆盖</button>
        <button type="button" @click="workspaceStore.resolveConflict('rename')">重命名</button>
        <button type="button" @click="workspaceStore.resolveConflict('skip')">跳过</button>
        <button type="button" class="cancel" @click="workspaceStore.cancelConflict()">取消</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.conflict-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.42);
}

.conflict-dialog {
  width: min(340px, calc(100vw - 32px));
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-floating);
}

.conflict-dialog h2 {
  margin: 0 0 var(--space-8);
  color: var(--color-text);
  font-size: calc(14px * var(--font-scale));
}

.conflict-dialog p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.5;
}

.conflict-file-list {
  max-height: 140px;
  margin: var(--space-8) 0;
  padding-left: var(--space-12);
  overflow: auto;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.7;
}

.conflict-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-6);
  margin-top: var(--space-12);
}

.conflict-actions button {
  height: 30px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: calc(12px * var(--font-scale));
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    border-color var(--transition-fast);
}

.conflict-actions button:hover {
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.conflict-actions .cancel {
  border-color: transparent;
  color: var(--color-text-tertiary);
}
</style>
