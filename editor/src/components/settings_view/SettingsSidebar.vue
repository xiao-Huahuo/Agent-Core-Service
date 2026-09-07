<!--
  Settings sidebar component.

  Usage:
  Receives the tab metadata and active key from SettingsView, then emits the
  selected key when the user switches sections.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'

export type SettingsTabKey = 'basic' | 'appearance' | 'llm' | 'tools' | 'terminal' | 'web' | 'memory' | 'graph' | 'safety' | 'storage' | 'floating' | 'skills' | 'mcp'

/** Semantic icons remain local through the shared DSH + morphicons registry. */
const TAB_ICONS: Record<SettingsTabKey, string> = {
  basic: 'settings',
  appearance: 'visibility',
  llm: 'psychology',
  tools: 'build',
  terminal: 'code',
  web: 'language',
  memory: 'book',
  graph: 'hub',
  safety: 'shield',
  storage: 'ingest',
  floating: 'open-in-full',
  skills: 'auto-awesome',
  mcp: 'build',
}

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
      <IcIcon class="sidebar-tab-icon" :name="TAB_ICONS[tab.key]" :size="16" />
      <span>{{ tab.label }}</span>
    </button>
  </aside>
</template>
