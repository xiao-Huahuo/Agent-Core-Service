<!--
  Tool settings section with collapsible categories.

  Usage:
  Renders Agent tool availability switches grouped by category, with
  collapsible sections. SettingsView owns the backend update path.
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import type { ToolGroup } from '@/api/settings'

defineProps<{
  groups: ToolGroup[]
  toolsMsg: string
}>()

defineEmits<{
  toggleTool: [toolName: string]
}>()

const collapsedCategories = ref<Set<string>>(new Set())

function toggleCategory(category: string) {
  const next = new Set(collapsedCategories.value)
  if (next.has(category)) next.delete(category)
  else next.add(category)
  collapsedCategories.value = next
}
</script>

<template>
  <div class="setting-section">
    <h3>工具开关</h3>
    <p class="setting-hint toggle-hint">关闭后该工具将不会出现在 Agent 的工具列表中</p>
    <div class="tool-list">
      <template v-for="group in groups" :key="group.category">
        <div class="category-header" @click="toggleCategory(group.category)">
          <ChevronDown
            :size="14"
            class="collapse-icon"
            :class="{ collapsed: collapsedCategories.has(group.category) }"
          />
          <span class="category-name">{{ group.display_name }}</span>
          <span class="category-count">{{ group.tools.length }}</span>
        </div>
        <div v-if="!collapsedCategories.has(group.category)" class="category-tools">
          <div
            v-for="tool in group.tools"
            :key="tool.name"
            class="tool-row"
            :class="{ disabled: !tool.enabled }"
          >
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
        </div>
      </template>
      <p v-if="!groups.length" class="empty-hint">暂无可用工具</p>
    </div>
    <span v-if="toolsMsg" class="feedback">{{ toolsMsg }}</span>
  </div>
</template>

<style scoped>
.setting-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.setting-section h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: calc(15px * var(--font-scale));
  font-weight: 650;
}

.setting-hint {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: calc(11px * var(--font-scale));
}

.toggle-hint {
  margin-bottom: var(--space-4);
}

.tool-list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

/* Category header */
.category-header {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast);
}

.category-header:hover {
  background: var(--color-primary-softer);
}

.collapse-icon {
  flex: none;
  color: var(--color-text-tertiary);
  transition: transform 200ms;
}

.collapse-icon.collapsed {
  transform: rotate(-90deg);
}

.category-name {
  flex: 1;
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
  letter-spacing: 0.5px;
}

.category-count {
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
}

.tool-row {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  padding: var(--space-8) var(--space-10);
  border-bottom: 1px solid var(--color-border);
  transition: opacity 150ms;
}

.tool-row:last-child {
  border-bottom: 0;
}

.tool-row.disabled {
  opacity: 0.5;
}

.tool-row.disabled .tool-name {
  text-decoration: line-through;
}

.tool-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.tool-name {
  color: var(--color-text-primary);
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
}

.tool-desc {
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-row input[type="checkbox"] {
  flex: none;
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80px;
  margin: 0;
  padding: var(--space-16);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.feedback {
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
}
</style>
