<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchSystemPrompts, addSystemPromptEntry, deleteSystemPromptEntry, fetchMemories, addMemory, deleteMemory, fetchLLMConfig, saveLLMConfig, fetchWebSearchConfig, saveWebSearchConfig, fetchAvailableTools, saveDisabledTools } from '@/api/settings'
import type { SystemPromptEntry, MemoryEntry, ToolEntry } from '@/api/settings'
import BasicSettingsSection from '@/components/settings_view/BasicSettingsSection.vue'
import LlmSettingsSection from '@/components/settings_view/LlmSettingsSection.vue'
import MemorySettingsSection from '@/components/settings_view/MemorySettingsSection.vue'
import SettingsSidebar from '@/components/settings_view/SettingsSidebar.vue'
import type { SettingsTabKey } from '@/components/settings_view/SettingsSidebar.vue'
import ToolsSettingsSection from '@/components/settings_view/ToolsSettingsSection.vue'
import WebSearchSettingsSection from '@/components/settings_view/WebSearchSettingsSection.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ThemeMode } from '@/types/settings'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

const activeTab = ref<SettingsTabKey>('basic')

const tabs = [
  { key: 'basic' as const, label: '基础设置' },
  { key: 'llm' as const, label: 'LLM 配置' },
  { key: 'tools' as const, label: '工具配置' },
  { key: 'web' as const, label: '联网配置' },
  { key: 'memory' as const, label: '记忆与指令' },
]

/* ---- Basic settings ---- */

const libraryNameDraft = ref(settingsStore.activeKnowledgeLibrary?.name ?? '')
const knowledgeDirDraft = ref(settingsStore.profile.knowledgeDir)
const watchEnabledDraft = ref(settingsStore.profile.knowledgeWatchEnabled)
const autoIngestOnUploadDraft = ref(Boolean(settingsStore.profile.autoIngestOnUpload))
const ocrEnabledDraft = ref(Boolean(settingsStore.profile.ocrEnabled))
const knowledgeIgnorePatternsDraft = ref(settingsStore.profile.knowledgeIgnorePatterns ?? '')
const uiFontFamiliesDraft = ref<string[]>([...(settingsStore.profile.uiFontFamilies ?? [])])
const textFontFamiliesDraft = ref<string[]>([...(settingsStore.profile.textFontFamilies ?? [])])
const availableFontFamilies = ref<string[]>([])
const fontsLoading = ref(false)
const saving = ref(false)
const saveError = ref('')
const saveMessage = ref('')

const hasChanges = computed(() => {
  return (
    knowledgeDirDraft.value !== settingsStore.profile.knowledgeDir ||
    libraryNameDraft.value !== (settingsStore.activeKnowledgeLibrary?.name ?? '') ||
    watchEnabledDraft.value !== settingsStore.profile.knowledgeWatchEnabled ||
    autoIngestOnUploadDraft.value !== Boolean(settingsStore.profile.autoIngestOnUpload) ||
    ocrEnabledDraft.value !== Boolean(settingsStore.profile.ocrEnabled) ||
    knowledgeIgnorePatternsDraft.value !== (settingsStore.profile.knowledgeIgnorePatterns ?? '')
  )
})

watch(
  () => settingsStore.activeKnowledgeLibrary?.name ?? '',
  (value) => { libraryNameDraft.value = value },
)

watch(
  () => settingsStore.profile.knowledgeDir,
  (value) => { knowledgeDirDraft.value = value },
)

watch(
  () => settingsStore.profile.autoIngestOnUpload,
  (value) => { autoIngestOnUploadDraft.value = Boolean(value) },
)

watch(
  () => settingsStore.profile.ocrEnabled,
  (value) => { ocrEnabledDraft.value = Boolean(value) },
)

watch(
  () => settingsStore.profile.knowledgeIgnorePatterns,
  (value) => { knowledgeIgnorePatternsDraft.value = value ?? '' },
)

watch(
  () => settingsStore.profile.uiFontFamilies,
  (value) => { uiFontFamiliesDraft.value = [...(value ?? [])] },
)

watch(
  () => settingsStore.profile.textFontFamilies,
  (value) => { textFontFamiliesDraft.value = [...(value ?? [])] },
)

async function loadAvailableFonts() {
  fontsLoading.value = true
  const fallbackFonts = [
    'Microsoft YaHei UI',
    'Microsoft YaHei',
    'PingFang SC',
    'Noto Sans SC',
    'JetBrains Mono',
    'Hack',
    'Cascadia Code',
    'Arial',
    'Segoe UI',
    'system-ui',
  ]
  try {
    const desktopFonts = await window.agentEditorDesktop?.listFontFamilies?.()
    const fonts = desktopFonts?.length ? desktopFonts : fallbackFonts
    availableFontFamilies.value = [...new Set(fonts.map((item) => item.trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b))
  } catch {
    availableFontFamilies.value = fallbackFonts
  } finally {
    fontsLoading.value = false
  }
}

async function handleSaveFontFamilies(payload: { target: 'ui' | 'text'; families: string[] }) {
  const nextUiFontFamilies = payload.target === 'ui' ? payload.families : uiFontFamiliesDraft.value
  const nextTextFontFamilies = payload.target === 'text' ? payload.families : textFontFamiliesDraft.value
  uiFontFamiliesDraft.value = [...nextUiFontFamilies]
  textFontFamiliesDraft.value = [...nextTextFontFamilies]
  try {
    await settingsStore.saveFontSettings({
      uiFontFamilies: nextUiFontFamilies,
      textFontFamilies: nextTextFontFamilies,
    })
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : '保存字体设置失败'
  }
}

async function saveProfile() {
  saving.value = true
  saveError.value = ''
  saveMessage.value = ''
  const nextKnowledgeDir = knowledgeDirDraft.value.trim() || settingsStore.profile.knowledgeDir
  const nextLibraryName = libraryNameDraft.value.trim()
  const ignorePatternsChanged = knowledgeIgnorePatternsDraft.value !== (settingsStore.profile.knowledgeIgnorePatterns ?? '')
  const ocrEnabledChanged = ocrEnabledDraft.value !== Boolean(settingsStore.profile.ocrEnabled)
  try {
    settingsStore.updateProfile({ knowledgeWatchEnabled: watchEnabledDraft.value })
    if (nextKnowledgeDir !== settingsStore.profile.knowledgeDir) {
      await settingsStore.switchKnowledgeRoot(nextKnowledgeDir)
    }
    if (nextLibraryName && nextLibraryName !== (settingsStore.activeKnowledgeLibrary?.name ?? '')) {
      await settingsStore.renameActiveKnowledgeLibrary(nextLibraryName)
    }
    if (
      autoIngestOnUploadDraft.value !== Boolean(settingsStore.profile.autoIngestOnUpload) ||
      ocrEnabledChanged ||
      ignorePatternsChanged
    ) {
      const result = await settingsStore.saveKnowledgeIngestionSettings({
        autoIngestOnUpload: autoIngestOnUploadDraft.value,
        ocrEnabled: ocrEnabledDraft.value,
        knowledgeIgnorePatterns: knowledgeIgnorePatternsDraft.value,
      })
      if (result?.restart_required) {
        saveMessage.value = 'OCR 设置已保存, 重启后生效'
      }
    }
    if (ignorePatternsChanged || ocrEnabledChanged) {
      await workspaceStore.loadKnowledgeTree()
    }
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    saving.value = false
  }
}

const themeOptions: Array<{ value: ThemeMode; label: string }> = [
  { value: 'dark', label: '深色' },
  { value: 'light', label: '浅色' },
  { value: 'system', label: '跟随系统' },
]

/* ---- System prompts ---- */

const promptEntries = ref<SystemPromptEntry[]>([])
const newPromptContent = ref('')
const addingPrompt = ref(false)
const promptMsg = ref('')

/* ---- Long-term memories ---- */

const memories = ref<MemoryEntry[]>([])
const newMemoryContent = ref('')
const addingMemory = ref(false)
const memoryMsg = ref('')

function showMessage(refObj: ReturnType<typeof ref<string>>, text: string, duration = 2000) {
  refObj.value = text
  setTimeout(() => { refObj.value = '' }, duration)
}

async function loadAgentSettings() {
  if (!settingsStore.profile.userId) return
  try {
    const [promptRes, memoryRes] = await Promise.all([
      fetchSystemPrompts(settingsStore.profile.userId),
      fetchMemories(settingsStore.profile.userId),
    ])
    promptEntries.value = promptRes.entries ?? []
    memories.value = memoryRes ?? []
  } catch { /* API not critical for workspace */ }
}

async function handleAddPrompt() {
  const content = newPromptContent.value.trim()
  if (!content || !settingsStore.profile.userId) return
  addingPrompt.value = true
  try {
    await addSystemPromptEntry(settingsStore.profile.userId, content)
    newPromptContent.value = ''
    await loadAgentSettings()
    showMessage(promptMsg, '已添加')
  } catch {
    showMessage(promptMsg, '添加失败')
  } finally {
    addingPrompt.value = false
  }
}

async function handleDeletePrompt(promptId: string) {
  try {
    await deleteSystemPromptEntry(promptId)
    await loadAgentSettings()
    showMessage(promptMsg, '已删除')
  } catch {
    showMessage(promptMsg, '删除失败')
  }
}

async function handleAddMemory() {
  const content = newMemoryContent.value.trim()
  if (!content || !settingsStore.profile.userId) return
  addingMemory.value = true
  try {
    await addMemory(settingsStore.profile.userId, content)
    newMemoryContent.value = ''
    await loadAgentSettings()
    showMessage(memoryMsg, '已添加')
  } catch {
    showMessage(memoryMsg, '添加失败')
  } finally {
    addingMemory.value = false
  }
}

async function handleDeleteMemory(memoryId: string) {
  try {
    await deleteMemory(memoryId)
    await loadAgentSettings()
    showMessage(memoryMsg, '已删除')
  } catch {
    showMessage(memoryMsg, '删除失败')
  }
}

/* ---- Web search config ---- */

const proxyUrlDraft = ref('')
const webSearchEnabledDraft = ref(false)
const webSearchSaving = ref(false)
const webSearchMsg = ref('')

async function loadWebSearchConfig() {
  if (!settingsStore.profile.userId) return
  try {
    const cfg = await fetchWebSearchConfig(settingsStore.profile.userId)
    proxyUrlDraft.value = cfg.proxy_url || ''
    webSearchEnabledDraft.value = cfg.web_search_enabled
  } catch { /* ignore */ }
}

async function handleSaveWebSearch() {
  if (!settingsStore.profile.userId) return
  webSearchSaving.value = true
  webSearchMsg.value = ''
  try {
    await saveWebSearchConfig(settingsStore.profile.userId, {
      proxyUrl: proxyUrlDraft.value || undefined,
      webSearchEnabled: webSearchEnabledDraft.value,
    })
    settingsStore.updateProfile({
      proxyUrl: proxyUrlDraft.value,
      webSearchEnabled: webSearchEnabledDraft.value,
    })
    showMessage(webSearchMsg, '已保存')
  } catch {
    showMessage(webSearchMsg, '保存失败')
  } finally {
    webSearchSaving.value = false
  }
}

/* ---- LLM model config ---- */

const largeModelName = ref('')
const largeBaseUrl = ref('')
const largeApiKey = ref('')
const smallModelName = ref('')
const smallBaseUrl = ref('')
const smallApiKey = ref('')
const showLargeKey = ref(false)
const showSmallKey = ref(false)
const modelSaving = ref(false)
const modelMsg = ref('')
const modelEditing = ref(false)
const modelConfigSaved = computed(() => !!(largeModelName.value || largeBaseUrl.value || largeApiKey.value))

async function loadModelConfig() {
  if (!settingsStore.profile.userId) return
  try {
    const cfg = await fetchLLMConfig(settingsStore.profile.userId)
    if (!cfg || !cfg.user_id) return
    largeModelName.value = cfg.model_name || ''
    largeBaseUrl.value = cfg.base_url || ''
    largeApiKey.value = cfg.api_key || ''
    smallModelName.value = cfg.small_model_name || ''
    smallBaseUrl.value = cfg.small_base_url || ''
    smallApiKey.value = cfg.small_api_key || ''
  } catch { /* ignore */ }
}

async function handleSaveModel() {
  if (!settingsStore.profile.userId) return
  modelSaving.value = true
  modelMsg.value = ''
  try {
    await saveLLMConfig(settingsStore.profile.userId, {
      apiKey: largeApiKey.value || undefined,
      baseUrl: largeBaseUrl.value || undefined,
      modelName: largeModelName.value || undefined,
      smallApiKey: smallApiKey.value || undefined,
      smallBaseUrl: smallBaseUrl.value || undefined,
      smallModelName: smallModelName.value || undefined,
    })
    modelEditing.value = false
    showMessage(modelMsg, '已保存')
  } catch {
    showMessage(modelMsg, '保存失败')
  } finally {
    modelSaving.value = false
  }
}

/* ---- Tool management ---- */

const tools = ref<ToolEntry[]>([])
const toolsMsg = ref('')

async function loadTools() {
  if (!settingsStore.profile.userId) return
  try {
    const res = await fetchAvailableTools(settingsStore.profile.userId)
    tools.value = res.tools ?? []
  } catch {
    tools.value = []
  }
}

async function handleToggleTool(toolName: string) {
  if (!settingsStore.profile.userId) return
  const tool = tools.value.find(t => t.name === toolName)
  if (tool) tool.enabled = !tool.enabled
  try {
    const disabled = tools.value.filter(t => !t.enabled).map(t => t.name)
    await saveDisabledTools(settingsStore.profile.userId, disabled)
  } catch {
    if (tool) tool.enabled = !tool.enabled
    showMessage(toolsMsg, '保存失败')
  }
}

const sortedTools = computed(() => {
  return [...tools.value].sort((a, b) => {
    if (a.enabled !== b.enabled) return a.enabled ? -1 : 1
    return a.display_name.localeCompare(b.display_name)
  })
})

onMounted(() => {
  loadAvailableFonts()
  loadAgentSettings()
  loadModelConfig()
  loadWebSearchConfig()
  loadTools()
})
</script>

<template>
  <div class="settings-page">
    <SettingsSidebar
      :active-tab="activeTab"
      :tabs="tabs"
      @select="activeTab = $event"
    />

    <div class="settings-body">
      <BasicSettingsSection
        v-if="activeTab === 'basic'"
        v-model:auto-ingest-on-upload-draft="autoIngestOnUploadDraft"
        v-model:knowledge-dir-draft="knowledgeDirDraft"
        v-model:knowledge-ignore-patterns-draft="knowledgeIgnorePatternsDraft"
        v-model:library-name-draft="libraryNameDraft"
        v-model:ocr-enabled-draft="ocrEnabledDraft"
        v-model:text-font-families-draft="textFontFamiliesDraft"
        v-model:ui-font-families-draft="uiFontFamiliesDraft"
        v-model:watch-enabled-draft="watchEnabledDraft"
        :available-font-families="availableFontFamilies"
        :fonts-loading="fontsLoading"
        :has-changes="hasChanges"
        :save-error="saveError"
        :save-message="saveMessage"
        :saving="saving"
        :show-index-column="settingsStore.showIndexColumn"
        :theme-mode="settingsStore.themeMode"
        :theme-options="themeOptions"
        @save="saveProfile"
        @save-font-families="handleSaveFontFamilies"
        @set-show-index-column="settingsStore.setShowIndexColumn"
        @set-theme-mode="settingsStore.setThemeMode"
      />

      <LlmSettingsSection
        v-if="activeTab === 'llm'"
        v-model:large-api-key="largeApiKey"
        v-model:large-base-url="largeBaseUrl"
        v-model:large-model-name="largeModelName"
        v-model:model-editing="modelEditing"
        v-model:show-large-key="showLargeKey"
        v-model:show-small-key="showSmallKey"
        v-model:small-api-key="smallApiKey"
        v-model:small-base-url="smallBaseUrl"
        v-model:small-model-name="smallModelName"
        :model-config-saved="modelConfigSaved"
        :model-msg="modelMsg"
        :model-saving="modelSaving"
        @cancel="modelEditing = false; loadModelConfig()"
        @save="handleSaveModel"
      />

      <ToolsSettingsSection
        v-if="activeTab === 'tools'"
        :tools="sortedTools"
        :tools-msg="toolsMsg"
        @toggle-tool="handleToggleTool"
      />

      <WebSearchSettingsSection
        v-if="activeTab === 'web'"
        v-model:proxy-url-draft="proxyUrlDraft"
        v-model:web-search-enabled-draft="webSearchEnabledDraft"
        :web-search-msg="webSearchMsg"
        :web-search-saving="webSearchSaving"
        @save="handleSaveWebSearch"
      />

      <MemorySettingsSection
        v-if="activeTab === 'memory'"
        v-model:new-memory-content="newMemoryContent"
        v-model:new-prompt-content="newPromptContent"
        :adding-memory="addingMemory"
        :adding-prompt="addingPrompt"
        :memories="memories"
        :memory-msg="memoryMsg"
        :prompt-entries="promptEntries"
        :prompt-msg="promptMsg"
        @add-memory="handleAddMemory"
        @add-prompt="handleAddPrompt"
        @delete-memory="handleDeleteMemory"
        @delete-prompt="handleDeletePrompt"
      />
    </div>
  </div>
</template>

<style>
.settings-page {
  display: flex;
  height: 100%;
  overflow: hidden;
  background:
    linear-gradient(180deg, var(--color-chrome-bg-top), var(--color-chrome-bg-bottom)),
    var(--color-chrome-bg-solid);
}

.settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 120px;
  flex-shrink: 0;
  padding: var(--space-12) var(--space-8);
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
}

.sidebar-tab {
  display: block;
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  transition: background 150ms, color 150ms;
}

.sidebar-tab:hover {
  background: var(--color-primary-softer);
  color: var(--color-text-primary);
}

.sidebar-tab.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.settings-body {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: var(--space-16) var(--space-20);
  font-size: 13px;
}

.setting-section h3 {
  margin: 0 0 var(--space-10);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.setting-row {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  margin-bottom: var(--space-8);
}

.setting-row label {
  flex-shrink: 0;
  width: 72px;
  color: var(--color-text);
  font-size: 13px;
}

.setting-row > input {
  flex: 1;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: 12px;
  outline: none;
}

.setting-row > input:focus {
  border-color: var(--color-primary);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: var(--space-10);
}

.toggle-row label {
  width: 72px;
}

.toggle-row input[type="checkbox"] {
  position: relative;
  width: 28px;
  height: 16px;
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

.toggle-row input[type="checkbox"]::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--color-text-muted);
  transition: transform 200ms, background 200ms;
}

.toggle-row input[type="checkbox"]:checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.toggle-row input[type="checkbox"]:checked::before {
  transform: translateX(12px);
  background: #fff;
}

.ignore-row {
  align-items: flex-start;
}

.ignore-row textarea {
  flex: 1;
  min-height: 86px;
  padding: var(--space-8) var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: 12px;
  line-height: 1.5;
  outline: none;
  resize: vertical;
}

.ignore-row textarea:focus {
  border-color: var(--color-primary);
}

.setting-hint {
  margin: -2px 0 var(--space-8) 82px;
  color: var(--color-text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.font-family-control {
  position: relative;
  margin-bottom: var(--space-10);
  padding-left: 82px;
}

.font-family-header {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  margin-bottom: var(--space-6);
}

.font-family-header label {
  width: 72px;
  margin-left: -82px;
  color: var(--color-text);
  font-size: 13px;
}

.font-family-header span {
  color: var(--color-text-muted);
  font-size: 11px;
}

.font-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  min-width: 0;
}

.font-chip,
.font-add-button {
  min-height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.font-chip:hover,
.font-add-button:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.font-picker-popover {
  position: absolute;
  top: calc(100% + 4px);
  left: 82px;
  z-index: 30;
  width: min(360px, calc(100vw - 180px));
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
}

.font-picker-popover input {
  width: 100%;
  height: 30px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-surface-raised);
  color: var(--color-text);
  font-size: 12px;
}

.font-picker-popover input:focus {
  border-color: var(--color-primary);
}

.font-option-list {
  display: grid;
  gap: 2px;
  max-height: 260px;
  margin-top: var(--space-6);
  overflow: auto;
}

.font-option-list button {
  min-height: 28px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
}

.font-option-list button:hover {
  background: var(--color-primary-softer);
  color: var(--color-text);
}

.font-empty {
  margin: var(--space-8);
  color: var(--color-text-muted);
  font-size: 12px;
}

/* Theme */
.theme-row {
  display: flex;
  gap: var(--space-6);
}

.theme-row button {
  height: 28px;
  padding: 0 var(--space-16);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.theme-row button.active {
  background: transparent;
  font-weight: 600;
}

.theme-row button.theme-dark.active {
  border-color: #EB2463;
  color: #EB2463;
}

.theme-row button.theme-light.active {
  border-color: #4224EB;
  color: #4224EB;
}

.theme-row button.theme-system.active {
  position: relative;
  border: 1px solid transparent;
  background: transparent;
  color: #4224EB;
  font-weight: 600;
}

.theme-row button.theme-system.active::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 999px;
  padding: 1px;
  background: linear-gradient(90deg, #EB2463, #4224EB);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

/* Model */
.model-block {
  margin-bottom: var(--space-10);
}

.model-block > input {
  display: block;
  width: 100%;
  height: 28px;
  margin-bottom: var(--space-6);
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

.model-block > input:focus {
  border-color: var(--color-primary);
}

.model-block > input.readonly {
  border-color: transparent;
  background: transparent;
  cursor: default;
}

.key-row {
  display: flex;
  gap: var(--space-4);
}

.key-row input {
  flex: 1;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

.key-row input:focus {
  border-color: var(--color-primary);
}

.key-row input.readonly {
  border-color: transparent;
  background: transparent;
  cursor: default;
}

.toggle-key {
  flex-shrink: 0;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font-family: var(--font-code);
  font-size: 11px;
  cursor: pointer;
}

.toggle-key:hover {
  color: var(--color-text);
  border-color: var(--color-primary);
}

.model-actions {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.hint-text {
  color: var(--color-text-muted);
  font-size: 11px;
  line-height: 1.4;
}

.feedback.error {
  color: var(--color-danger);
}

.save-model-btn {
  height: 28px;
  padding: 0 var(--space-16);
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  font-family: var(--font-code);
  font-size: 12px;
  cursor: pointer;
}

.save-model-btn:hover:not(:disabled) {
  background: var(--color-primary);
  color: #fff;
}

.save-model-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.edit-model-btn {
  height: 28px;
  padding: 0 var(--space-16);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.edit-model-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.cancel-model-btn {
  height: 28px;
  padding: 0 var(--space-14);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
}

.cancel-model-btn:hover {
  color: var(--color-text);
}

/* Input row for add */
.input-row {
  display: flex;
  gap: var(--space-4);
}

.input-row input {
  flex: 1;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: 12px;
  outline: none;
}

.input-row input:focus {
  border-color: var(--color-primary);
}

.add-btn {
  flex-shrink: 0;
  height: 28px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  font-family: var(--font-code);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.add-btn:hover:not(:disabled) {
  background: var(--color-primary);
  color: #fff;
}

.add-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.feedback {
  margin: var(--space-4) 0 0;
  color: var(--color-primary);
  font-size: 12px;
}

/* Entry list */
.entry-list {
  list-style: none;
  margin: var(--space-6) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.entry-row {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-4) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.entry-text {
  flex: 1;
  font-family: var(--font-code);
  font-size: 12px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-del {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 14px;
  cursor: pointer;
}

.entry-del:hover {
  color: var(--color-danger);
  border-color: rgba(255, 95, 95, 0.4);
  background: rgba(255, 95, 95, 0.08);
}

/* Tool management */
.tool-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tool-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  transition: opacity 150ms;
}

.tool-row.disabled {
  opacity: 0.55;
}

.tool-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tool-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
}

.tool-desc {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-row input[type="checkbox"] {
  position: relative;
  width: 28px;
  height: 16px;
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

.tool-row input[type="checkbox"]::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--color-text-muted);
  transition: transform 200ms, background 200ms;
}

.tool-row input[type="checkbox"]:checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.tool-row input[type="checkbox"]:checked::before {
  transform: translateX(12px);
  background: #fff;
}

.toggle-hint {
  margin: -2px 0 var(--space-8) 0 !important;
}

.empty-hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: var(--space-4) 0;
}
</style>
