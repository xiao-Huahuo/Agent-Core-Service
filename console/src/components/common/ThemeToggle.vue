<!--
  主题切换按钮 — macOS 窗口风格。
-->

<script setup>
import { Sun, Moon } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
</script>

<template>
  <button
    class="theme-toggle"
    :title="settingsStore.themeMode === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
    @click="settingsStore.toggleTheme()"
  >
    <Sun v-if="settingsStore.themeMode === 'dark'" :size="13" />
    <Moon v-else :size="13" />
  </button>
</template>

<style scoped>
.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  transition: all var(--transition-fast);
}

.theme-toggle:hover {
  color: var(--color-text-primary);
  border-color: var(--color-border-strong);
  background: var(--color-bg-hover);
}
</style>
