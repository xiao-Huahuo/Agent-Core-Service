<!--
  Agent tool registry panel with collapsible categories.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, RefreshCw, Search } from 'lucide-vue-next'

import { fetchAgentTools, type AgentToolInfo } from '@/api/tools'
import { fetchAvailableTools, saveDisabledTools, type ToolGroup } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

interface AugmentedTool extends AgentToolInfo {
  enabled: boolean
}

interface AugmentedGroup {
  category: string
  display_name: string
  tools: AugmentedTool[]
}

const agentTools = ref<AgentToolInfo[]>([])
const groupsFromApi = ref<ToolGroup[]>([])
const enabledMap = ref<Record<string, boolean>>({})
const loading = ref(false)
const errorText = ref('')
const query = ref('')
const selectedName = ref('')
const collapsedCategories = ref<Set<string>>(new Set())

/** Map agent tool info into each group's tools, merging enabled status. */
const groupedTools = computed<AugmentedGroup[]>(() => {
  const agentMap = new Map(agentTools.value.map(t => [t.name, t]))
  return groupsFromApi.value.map(g => ({
    category: g.category,
    display_name: g.display_name,
    tools: g.tools
      .map(t => {
        const info = agentMap.get(t.name)
        if (!info) return null
        return { ...info, enabled: t.enabled }
      })
      .filter((t): t is AugmentedTool => t !== null),
  }))
})

const filteredGroups = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return groupedTools.value
  return groupedTools.value
    .map(g => {
      const filtered = g.tools.filter(t =>
        `${t.name} ${t.display_name} ${t.description}`.toLowerCase().includes(q)
      )
      return filtered.length ? { ...g, tools: filtered } : null
    })
    .filter((g): g is AugmentedGroup => g !== null)
})

const totalArguments = computed(() => {
  return agentTools.value.reduce((sum, t) => sum + t.argument_count, 0)
})

const selectedTool = computed(() => {
  for (const g of filteredGroups.value) {
    const found = g.tools.find(t => t.name === selectedName.value)
    if (found) return found
  }
  return filteredGroups.value[0]?.tools[0] ?? null
})

const requiredArgs = computed(() => {
  return new Set(selectedTool.value?.args_schema?.required ?? [])
})

const selectedProperties = computed(() => {
  const properties = selectedTool.value?.args_schema?.properties ?? {}
  return Object.entries(properties).map(([name, schema]) => ({
    name,
    type: (schema as { type?: string }).type || 'unknown',
    description: (schema as { description?: string }).description || '',
    required: requiredArgs.value.has(name),
  }))
})

function toggleCategory(category: string) {
  const next = new Set(collapsedCategories.value)
  if (next.has(category)) next.delete(category)
  else next.add(category)
  collapsedCategories.value = next
}

async function loadTools() {
  loading.value = true
  errorText.value = ''
  try {
    const [agentPayload, settingsPayload] = await Promise.all([
      fetchAgentTools(),
      fetchAvailableTools(settingsStore.profile.userId || ''),
    ])
    agentTools.value = agentPayload.tools
    groupsFromApi.value = settingsPayload.groups ?? []
    const map: Record<string, boolean> = {}
    for (const g of settingsPayload.groups ?? []) {
      for (const t of g.tools) map[t.name] = t.enabled
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
  const wasEnabled = enabledMap.value[toolName] !== false
  enabledMap.value = { ...enabledMap.value, [toolName]: !wasEnabled }
  try {
    const userId = settingsStore.profile.userId
    if (!userId) return
    const disabled = Object.entries(enabledMap.value)
      .filter(([, enabled]) => !enabled)
      .map(([name]) => name)
    await saveDisabledTools(userId, disabled)
  } catch {
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
          <span>{{ agentTools.length }} tools</span>
          <span>{{ totalArguments }} args</span>
          <span>{{ filteredGroups.reduce((s, g) => s + g.tools.length, 0) }} visible</span>
        </div>
        <div class="registry-search">
          <Search :size="14" />
          <input v-model="query" type="text" placeholder="搜索工具" />
        </div>
        <button class="icon-button" type="button" title="刷新" :disabled="loading" @click="loadTools">
          <RefreshCw :size="15" />
        </button>
      </div>

      <div class="panel-surface">
        <p v-if="errorText" class="error-line">{{ errorText }}</p>

        <div class="registry-grid">
          <aside class="tool-list" aria-label="工具列表">
            <div v-if="loading" class="empty-state"><span>$ 正在读取</span></div>
            <template v-for="group in filteredGroups" :key="group.category">
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
                  class="tool-list-item"
                  :class="{
                    active: selectedTool?.name === tool.name,
                    disabled: !tool.enabled,
                  }"
                >
                  <button class="tool-row" type="button" @click="selectTool(tool)">
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
                    <span class="toggle-bg"></span>
                    <span class="toggle-thumb">
                      <span class="toggle-dot"></span>
                    </span>
                    <span v-if="!tool.enabled" class="disabled-badge">未启用</span>
                  </label>
                </div>
              </div>
            </template>
            <div v-if="!loading && filteredGroups.length === 0" class="empty-state">
              <span>$ 没有匹配的工具</span>
            </div>
          </aside>

          <main class="tool-detail">
            <div v-if="loading" class="empty-state"><span>$ 正在读取最终工具注册表</span></div>
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
            <div v-else class="empty-state"><span>$ 工具注册表为空</span></div>
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
.panel-heading { min-height: 24px; padding: 0 2px; }
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
.title-summary, .tool-name, .tool-meta, .detail-title code, .empty-state, .error-line { font-family: var(--font-ui); }
.arg-row, .schema-block { font-family: var(--font-text); }
.title-summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-10);
  min-width: 0;
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
}
h2 { margin: 0; color: var(--color-text-primary); font-size: calc(14px * var(--font-scale)); line-height: 1.2; }
.icon-button {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  border: 1px solid transparent; border-radius: 6px;
  background: transparent; color: var(--color-text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}
.icon-button:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  background: var(--color-primary-soft);
}
.icon-button:hover:not(:disabled) :deep(svg) { transform: rotate(90deg); }
.icon-button :deep(svg) { transition: transform 0.3s; }
.icon-button:disabled { opacity: 0.45; }
.registry-search {
  display: flex; align-items: center; gap: var(--space-8);
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border); border-radius: 999px;
  background: var(--color-surface-raised); color: var(--color-text-tertiary);
}
.registry-search input {
  width: 100%; height: 24px;
  border: 0; outline: 0; background: transparent;
  color: var(--color-text-primary); font: inherit;
}
.registry-search input::placeholder { font-size: calc(11px * var(--font-scale)); }
.registry-grid {
  display: grid;
  grid-template-columns: minmax(220px, 320px) minmax(0, 1fr);
  gap: var(--space-8);
  flex: 1; min-height: 0;
  padding: var(--space-10);
}
.tool-list, .tool-detail {
  min-height: 0;
  border: 1px solid var(--color-border); border-radius: 8px;
  background: var(--color-surface-raised); overflow: auto;
}
.tool-list { display: flex; flex-direction: column; }

/* Category header */
.category-header {
  display: flex; align-items: center; gap: var(--space-6);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer; user-select: none;
  transition: background var(--transition-fast);
}
.category-header:hover { background: var(--color-primary-softer); }
.collapse-icon { flex: none; color: var(--color-text-tertiary); transition: transform 200ms; }
.collapse-icon.collapsed { transform: rotate(-90deg); }
.category-name {
  flex: 1;
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.category-count { color: var(--color-text-tertiary); font-family: var(--font-ui); font-size: calc(10px * var(--font-scale)); }

.tool-list-item {
  display: flex; align-items: center;
  border-bottom: 1px solid var(--color-border);
  transition: opacity 150ms;
}
.tool-list-item.disabled { opacity: 0.5; }
.tool-list-item.disabled .tool-name { text-decoration: line-through; opacity: 0.7; }
.tool-list-item.active { background: var(--color-primary-softer); }
.tool-list-item.active .tool-row { box-shadow: none; }
.tool-row {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 0; background: transparent;
  color: var(--color-text-secondary);
  text-align: left; cursor: pointer;
}
.tool-row:hover { background: var(--color-primary-softer); color: var(--color-text-primary); }
.tool-name { overflow: hidden; font-size: calc(13px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.tool-meta { color: var(--color-text-tertiary); font-size: calc(10px * var(--font-scale)); }
.tool-toggle-label {
  position: relative;
  width: 32px;
  height: 20px;
  cursor: pointer;
  flex-shrink: 0;
}

.tool-toggle-label input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
}

.toggle-bg {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--color-text-muted);
  opacity: 0.3;
  transition: opacity 0.3s, background 0.3s;
  pointer-events: none;
}

.toggle-thumb {
  position: absolute;
  top: 0;
  left: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  transition: left 0.3s, background 0.3s;
  pointer-events: none;
  z-index: 1;
  margin: auto;
  bottom: 0;
}

.toggle-dot {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-surface);
  transition: transform 0.2s;
}

input:checked ~ .toggle-bg {
  opacity: 1;
  background: var(--color-primary);
}

input:checked ~ .toggle-thumb {
  left: 16px;
  background: var(--color-primary);
}

input:checked ~ .toggle-thumb .toggle-dot {
  transform: scale(0);
}
.disabled-badge { font-family: var(--font-ui); font-size: calc(9px * var(--font-scale)); color: var(--color-text-muted); white-space: nowrap; }
.tool-detail { padding: var(--space-12); }
.detail-title { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--space-8); }
.detail-display { color: var(--color-text-primary); font-size: calc(18px * var(--font-scale)); font-weight: 650; }
.detail-title code { color: var(--color-primary); font-size: calc(11px * var(--font-scale)); }
.detail-disabled-badge { font-family: var(--font-ui); font-size: calc(10px * var(--font-scale)); color: var(--color-text-tertiary); padding: 2px 6px; border: 1px solid var(--color-border); border-radius: 999px; }
.detail-description { margin: var(--space-10) 0 var(--space-12); color: var(--color-text-secondary); font-size: calc(13px * var(--font-scale)); line-height: 1.6; }
.arg-table { border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.arg-row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(80px, 0.7fr) minmax(80px, 0.7fr);
  gap: var(--space-8); padding: var(--space-8);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-secondary); font-size: calc(11px * var(--font-scale));
}
.arg-row:last-child { border-bottom: 0; }
.arg-head { color: var(--color-text-tertiary); text-transform: uppercase; }
.arg-name { color: var(--color-primary); }
.arg-desc { grid-column: 1 / -1; margin: 0; color: var(--color-text-tertiary); line-height: 1.5; }
.schema-block { margin: var(--space-12) 0 0; padding: var(--space-10); overflow: auto; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface-raised); color: var(--color-text-secondary); font-size: calc(11px * var(--font-scale)); line-height: 1.5; }
.empty-state, .error-line { color: var(--color-text-tertiary); font-size: calc(12px * var(--font-scale)); }
.empty-state { display: flex; align-items: center; justify-content: center; min-height: 160px; padding: var(--space-12); }
.error-line { flex-shrink: 0; margin: var(--space-8) var(--space-10) 0; padding: var(--space-8) var(--space-10); border: 1px solid color-mix(in srgb, var(--color-danger, #ff6b6b) 38%, var(--color-border)); border-radius: 6px; color: var(--color-danger, #ff6b6b); }
@media (max-width: 900px) {
  .registry-grid { grid-template-columns: minmax(0, 1fr); }
  .registry-heading { grid-template-columns: minmax(0, 1fr) auto; }
  .registry-search { grid-column: 1 / -1; }
  .tool-list { max-height: 240px; }
}
</style>
