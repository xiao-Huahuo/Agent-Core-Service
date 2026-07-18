<!--
  Settings sidebar component.

  Usage:
  Receives the tab metadata and active key from SettingsView, then emits the
  selected key when the user switches sections.
-->
<script setup lang="ts">
export type SettingsTabKey = 'basic' | 'appearance' | 'llm' | 'tools' | 'web' | 'memory'

defineProps<{
  tabs: Array<{ key: SettingsTabKey; label: string }>
  activeTab: SettingsTabKey
}>()

defineEmits<{
  select: [key: SettingsTabKey]
}>()
</script>

<template>
  <aside class="settings-sidebar">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="sidebar-tab"
      :class="{ active: activeTab === tab.key }"
      type="button"
      @click="$emit('select', tab.key)"
    >
      {{ tab.label }}
    </button>
  </aside>
</template>
