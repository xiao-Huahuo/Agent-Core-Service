<!--
  Tool settings section.

  Usage:
  Renders Agent tool availability switches. SettingsView owns the backend
  update path and passes sorted tool entries into this component.
-->
<script setup lang="ts">
import type { ToolEntry } from '@/api/settings'

defineProps<{
  tools: ToolEntry[]
  toolsMsg: string
}>()

defineEmits<{
  toggleTool: [toolName: string]
}>()
</script>

<template>
  <div class="setting-section">
    <h3>工具开关</h3>
    <p class="setting-hint toggle-hint">关闭后该工具将不会出现在 Agent 的工具列表中</p>
    <div class="tool-list">
      <div v-for="tool in tools" :key="tool.name" class="tool-row" :class="{ disabled: !tool.enabled }">
        <div class="tool-info">
          <span class="tool-name">{{ tool.display_name }}</span>
          <span class="tool-desc">{{ tool.description }}</span>
        </div>
        <input
          :checked="tool.enabled"
          type="checkbox"
          @change="$emit('toggleTool', tool.name)"
        />
      </div>
      <p v-if="!tools.length" class="empty-hint">暂无可用工具</p>
    </div>
    <span v-if="toolsMsg" class="feedback">{{ toolsMsg }}</span>
  </div>
</template>
