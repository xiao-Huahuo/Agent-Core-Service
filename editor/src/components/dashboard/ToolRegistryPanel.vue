<!--
  Agent tool registry panel.

  Usage:
  Shows the running Agent's final registered tools in the Debug page. The
  data comes from the backend registry after builtin and configured external
  tools have been merged. Disabled tools are sorted to the bottom with a
  toggle switch to enable/disable them directly.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCw, Search } from 'lucide-vue-next'

import { fetchAgentTools, type AgentToolInfo } from '@/api/tools'
import { fetchAvailableTools, saveDisabledTools } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

interface AugmentedTool extends AgentToolInfo {
  enabled: boolean
}

const tools = ref<AgentToolInfo[]>([])
const enabledMap = ref<Record<string, boolean>>({})
const loading = ref(false)
const errorText = ref('')
const query = ref('')
const selectedName = ref('')

const filteredTools = computed(() => {
  const q = query.value.trim().toLowerCase()
  let list = augmentedTools.value
  if (q) {
    list = list.filter((tool) => {
      return `${tool.name} ${tool.display_name} ${tool.description}`.toLowerCase().includes(q)
    })
  }
  // 已启用的排在前面，未启用的排在下面
  return [...list].sort((a, b) => {
    if (a.enabled !== b.enabled) return a.enabled ? -1 : 1
    return a.display_name.localeCompare(b.display_name)
  })
})

const augmentedTools = computed<AugmentedTool[]>(() => {
  return tools.value.map(t => ({
    ...t,
    enabled: enabledMap.value[t.name] !== false,
  }))
})

const selectedTool = computed(() => {
  return filteredTools.value.find((tool) => tool.name === selectedName.value) ?? filteredTools.value[0] ?? null
})

const totalArguments = computed(() => {
  return tools.value.reduce((sum, tool) => sum + tool.argument_count, 0)
})

const requiredArgs = computed(() => {
  return new Set(selectedTool.value?.args_schema?.required ?? [])
})

const selectedProperties = computed(() => {
  const properties = selectedTool.value?.args_schema?.properties ?? {}
  return Object.entries(properties).map(([name, schema]) => ({
    name,
    type: schema.type || 'unknown',
    description: schema.description || '',
    required: requiredArgs.value.has(name),
  }))
})

async function loadTools() {
  loading.value = true
  errorText.value = ''
  try {
    const [agentPayload, settingsPayload] = await Promise.all([
      fetchAgentTools(),
      fetchAvailableTools(settingsStore.profile.userId || ''),
    ])
    tools.value = agentPayload.tools
    const map: Record<string, boolean> = {}
    for (const t of settingsPayload.tools ?? []) {
      map[t.name] = t.enabled
    }
    enabledMap.value = map
    if (!selectedName.value && agentPayload.tools.length > 0) {
      selectedName.value = agentPayload.tools[0]!.name
    }
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '工具注册表加载失败'
  } finally {
    loading.value = false
  }
}

async function handleToggleTool(toolName: string) {
  const current = enabledMap.value[toolName]
  const wasEnabled = current !== false
  // Optimistic toggle
  enabledMap.value = { ...enabledMap.value, [toolName]: !wasEnabled }
  try {
    const userId = settingsStore.profile.userId
    if (!userId) return
    const disabled = Object.entries(enabledMap.value)
      .filter(([, enabled]) => !enabled)
      .map(([name]) => name)
    await saveDisabledTools(userId, disabled)
  } catch {
    // Revert on failure
    enabledMap.value = { ...enabledMap.value, [toolName]: wasEnabled }
  }
}

function selectTool(tool: AugmentedTool) {
  selectedName.value = tool.name
}

onMounted(() => {
  void loadTools()
})
</script>

<template>
  <div class="tool-registry-panel">
    <section class="registry-card">
      <div class="panel-heading registry-heading">
        <div class="title-summary">
          <h2>工具注册表</h2>
          <span>{{ tools.length }} tools</span>
          <span>{{ totalArguments }} args</span>
          <span>{{ filteredTools.length }} visible</span>
        </div>
        <div class="registry-search">
          <Search :size="14" />
          <input v-model="query" type="text" placeholder="搜索工具" />
        </div>
        <button class="icon-button" type="button" title="刷新工具注册表" :disabled="loading" @click="loadTools">
          <RefreshCw :size="15" />
        </button>
      </div>

      <div class="panel-surface">
        <p v-if="errorText" class="error-line">{{ errorText }}</p>

        <div class="registry-grid">
          <aside class="tool-list" aria-label="工具列表">
            <div
              v-for="tool in filteredTools"
              :key="tool.name"
              class="tool-list-item"
              :class="{
                active: selectedTool?.name === tool.name,
                disabled: !tool.enabled,
              }"
            >
              <button
                class="tool-row"
                type="button"
                @click="selectTool(tool)"
              >
                <span class="tool-name">{{ tool.display_name || tool.name }}</span>
                <span class="tool-meta">{{ tool.argument_count }} args</span>
              </button>
              <label
                class="tool-toggle-label"
                :title="tool.enabled ? '点击关闭' : '点击启用'"
                @click.stop
              >
                <input
                  :checked="tool.enabled"
                  type="checkbox"
                  @change="handleToggleTool(tool.name)"
                />
                <span v-if="!tool.enabled" class="disabled-badge">未启用</span>
              </label>
            </div>
            <div v-if="!loading && filteredTools.length === 0" class="empty-state">
              <span>$ 没有匹配的工具</span>
            </div>
          </aside>

          <main class="tool-detail">
            <div v-if="loading" class="empty-state">
              <span>$ 正在读取最终工具注册表</span>
            </div>
            <template v-else-if="selectedTool">
              <div class="detail-title">
                <span class="detail-display">{{ selectedTool.display_name || selectedTool.name }}</span>
                <code>{{ selectedTool.name }}</code>
                <span v-if="!selectedTool.enabled" class="detail-disabled-badge">未启用</span>
              </div>
              <p class="detail-description">{{ selectedTool.description }}</p>

              <div class="arg-table">
                <div class="arg-row arg-head">
                  <span>参数</span>
                  <span>类型</span>
                  <span>约束</span>
                </div>
                <div v-for="arg in selectedProperties" :key="arg.name" class="arg-row">
                  <span class="arg-name">{{ arg.name }}</span>
                  <span>{{ arg.type }}</span>
                  <span>{{ arg.required ? 'required' : 'optional' }}</span>
                  <p class="arg-desc">{{ arg.description || '无说明' }}</p>
                </div>
              </div>

              <pre class="schema-block">{{ JSON.stringify(selectedTool.args_schema, null, 2) }}</pre>
            </template>
            <div v-else class="empty-state">
              <span>$ 工具注册表为空</span>
            </div>
          </main>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tool-registry-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: var(--space-10);
  overflow: hidden;
}

.registry-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: var(--space-6);
}

.panel-heading {
  min-height: 24px;
  padding: 0 2px;
}

.registry-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 300px) auto;
  align-items: center;
  gap: var(--space-8);
}

.panel-surface {
  display: flex;
  flex: 1;
  min-height: 0;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-raised);
}

.title-summary,
.tool-name,
.tool-meta,
.detail-title code,
.empty-state,
.error-line {
  font-family: var(--font-ui);
}

.arg-row,
.schema-block {
  font-family: var(--font-text);
}

.title-summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-10);
  min-width: 0;
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
}

h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: calc(14px * var(--font-scale));
  line-height: 1.2;
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.icon-button:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  background: var(--color-primary-soft);
}

.icon-button:disabled {
  opacity: 0.45;
}

.registry-search {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text-tertiary);
}

.registry-search input {
  width: 100%;
  height: 24px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text-primary);
  font: inherit;
}

.registry-search input::placeholder {
  font-size: calc(11px * var(--font-scale));
}

.registry-grid {
  display: grid;
  grid-template-columns: minmax(220px, 320px) minmax(0, 1fr);
  gap: var(--space-8);
  flex: 1;
  min-height: 0;
  padding: var(--space-10);
}

.tool-list,
.tool-detail {
  min-height: 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-raised);
  overflow: auto;
}

.tool-list {
  display: flex;
  flex-direction: column;
}

.tool-list-item {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  transition: opacity 150ms;
}

.tool-list-item.disabled {
  opacity: 0.5;
}

.tool-list-item.disabled .tool-name {
  text-decoration: line-through;
  opacity: 0.7;
}

.tool-list-item.active {
  background: var(--color-primary-softer);
}

.tool-list-item.active .tool-row {
  box-shadow: none;
}

.tool-row {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
  cursor: pointer;
}

.tool-row:hover {
  background: var(--color-primary-softer);
  color: var(--color-text-primary);
}

.tool-name {
  overflow: hidden;
  font-size: calc(13px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-meta {
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
}

.tool-toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 var(--space-6) 0 0;
  cursor: pointer;
}

.tool-toggle-label input[type="checkbox"] {
  position: relative;
  width: 22px;
  height: 12px;
  margin: 0;
  flex: none;
  appearance: none;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  cursor: pointer;
  transition: background 200ms, border-color 200ms;
  flex-shrink: 0;
}

.tool-toggle-label input[type="checkbox"]::before {
  content: '';
  position: absolute;
  top: 1.5px;
  left: 1.5px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--color-text-muted);
  transition: transform 200ms, background 200ms;
}

.tool-toggle-label input[type="checkbox"]:checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.tool-toggle-label input[type="checkbox"]:checked::before {
  transform: translateX(10px);
  background: var(--color-bg-card);
}

.disabled-badge {
  font-family: var(--font-ui);
  font-size: calc(9px * var(--font-scale));
  color: var(--color-text-muted);
  white-space: nowrap;
}

.tool-detail {
  padding: var(--space-12);
}

.detail-title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-8);
}

.detail-display {
  color: var(--color-text-primary);
  font-size: calc(18px * var(--font-scale));
  font-weight: 650;
}

.detail-title code {
  color: var(--color-primary);
  font-size: calc(11px * var(--font-scale));
}

.detail-disabled-badge {
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  color: var(--color-text-tertiary);
  padding: 2px 6px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
}

.detail-description {
  margin: var(--space-10) 0 var(--space-12);
  color: var(--color-text-secondary);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
}

.arg-table {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.arg-row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(80px, 0.7fr) minmax(80px, 0.7fr);
  gap: var(--space-8);
  padding: var(--space-8);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
}

.arg-row:last-child {
  border-bottom: 0;
}

.arg-head {
  color: var(--color-text-tertiary);
  text-transform: uppercase;
}

.arg-name {
  color: var(--color-primary);
}

.arg-desc {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-text-tertiary);
  line-height: 1.5;
}

.schema-block {
  margin: var(--space-12) 0 0;
  padding: var(--space-10);
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.5;
}

.empty-state,
.error-line {
  color: var(--color-text-tertiary);
  font-size: calc(12px * var(--font-scale));
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: var(--space-12);
}

.error-line {
  flex-shrink: 0;
  margin: var(--space-8) var(--space-10) 0;
  padding: var(--space-8) var(--space-10);
  border: 1px solid color-mix(in srgb, var(--color-danger, #ff6b6b) 38%, var(--color-border));
  border-radius: 6px;
  color: var(--color-danger, #ff6b6b);
}

@media (max-width: 900px) {
  .registry-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .registry-heading {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .registry-search {
    grid-column: 1 / -1;
  }

  .tool-list {
    max-height: 240px;
  }
}
</style>
