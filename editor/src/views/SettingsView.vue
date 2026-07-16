<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchSystemPrompts, addSystemPromptEntry, deleteSystemPromptEntry, fetchMemories, addMemory, deleteMemory, fetchLLMConfig, saveLLMConfig, fetchWebSearchConfig, saveWebSearchConfig } from '@/api/settings'
import type { SystemPromptEntry, MemoryEntry } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ThemeMode } from '@/types/settings'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const libraryNameDraft = ref(settingsStore.activeKnowledgeLibrary?.name ?? '')
const knowledgeDirDraft = ref(settingsStore.profile.knowledgeDir)
const watchEnabledDraft = ref(settingsStore.profile.knowledgeWatchEnabled)
const autoIngestOnUploadDraft = ref(Boolean(settingsStore.profile.autoIngestOnUpload))
const ocrEnabledDraft = ref(Boolean(settingsStore.profile.ocrEnabled))
const knowledgeIgnorePatternsDraft = ref(settingsStore.profile.knowledgeIgnorePatterns ?? '')
const saving = ref(false)
const saveError = ref('')
const saveMessage = ref('')

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

onMounted(() => {
  loadAgentSettings()
  loadModelConfig()
  loadWebSearchConfig()
})

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

const themeOptions: Array<{ value: ThemeMode; label: string }> = [
  { value: 'dark', label: '深色' },
  { value: 'light', label: '浅色' },
  { value: 'system', label: '跟随系统' },
]

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
  (value) => {
    libraryNameDraft.value = value
  },
)

watch(
  () => settingsStore.profile.knowledgeDir,
  (value) => {
    knowledgeDirDraft.value = value
  },
)

watch(
  () => settingsStore.profile.autoIngestOnUpload,
  (value) => {
    autoIngestOnUploadDraft.value = Boolean(value)
  },
)

watch(
  () => settingsStore.profile.ocrEnabled,
  (value) => {
    ocrEnabledDraft.value = Boolean(value)
  },
)

watch(
  () => settingsStore.profile.knowledgeIgnorePatterns,
  (value) => {
    knowledgeIgnorePatternsDraft.value = value ?? ''
  },
)

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
</script>

<template>
  <div class="settings-page">
    <!-- 知识库 -->
    <section class="setting-section">
      <h3>知识库</h3>
      <div class="setting-row">
        <label>库名称</label>
        <input v-model="libraryNameDraft" spellcheck="false" />
      </div>
      <div class="setting-row">
        <label>知识目录</label>
        <input v-model="knowledgeDirDraft" spellcheck="false" />
      </div>
      <div class="setting-row toggle-row">
        <label>文件监听</label>
        <input v-model="watchEnabledDraft" type="checkbox" />
      </div>
      <div class="setting-row toggle-row">
        <label>自动灌库</label>
        <input v-model="autoIngestOnUploadDraft" type="checkbox" />
        <span class="hint-text">关闭时上传只进入文件树,点击 header 刷新或文件按钮才灌库</span>
      </div>
      <div class="setting-row toggle-row">
        <label>OCR</label>
        <input v-model="ocrEnabledDraft" type="checkbox" />
        <span class="hint-text">开启后需重启; 重启时会检查并预热 PaddleOCR 中英文模型</span>
      </div>
      <div class="setting-row ignore-row">
        <label>屏蔽区</label>
        <textarea
          v-model="knowledgeIgnorePatternsDraft"
          spellcheck="false"
          placeholder="# gitignore-like&#10;private/&#10;*.tmp&#10;!private/keep.md"
        ></textarea>
      </div>
      <p class="setting-hint">被屏蔽的文件不会入库; 已入库文件会在下次 Ingest 或单文件灌库时出库。</p>
      <div class="model-actions">
        <button class="save-model-btn" :disabled="saving || !hasChanges" @click="saveProfile">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <span v-if="saveMessage" class="feedback">{{ saveMessage }}</span>
        <span v-if="saveError" class="feedback error">{{ saveError }}</span>
      </div>
    </section>

    <!-- 主题 -->
    <section class="setting-section">
      <h3>主题</h3>
      <div class="theme-row">
        <button
          v-for="option in themeOptions"
          :key="option.value"
          :class="['theme-'+option.value, { active: settingsStore.themeMode === option.value }]"
          type="button"
          @click="settingsStore.setThemeMode(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </section>

    <!-- 语言模型 -->
    <section class="setting-section">
      <h3>语言模型</h3>
      <div class="model-block">
        <h4>大模型</h4>
        <input v-model="largeModelName" placeholder="deepseek-v4-flash" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <input v-model="largeBaseUrl" placeholder="https://api.deepseek.com" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <div class="key-row">
          <input v-model="largeApiKey" :type="showLargeKey ? 'text' : 'password'" placeholder="API Key" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
          <button class="toggle-key" @click="showLargeKey = !showLargeKey">{{ showLargeKey ? '隐藏' : '显示' }}</button>
        </div>
      </div>
      <div class="model-block">
        <h4>小模型</h4>
        <input v-model="smallModelName" placeholder="moonshot-v1-8k" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <input v-model="smallBaseUrl" placeholder="https://api.moonshot.cn/v1" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <div class="key-row">
          <input v-model="smallApiKey" :type="showSmallKey ? 'text' : 'password'" placeholder="API Key" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
          <button class="toggle-key" @click="showSmallKey = !showSmallKey">{{ showSmallKey ? '隐藏' : '显示' }}</button>
        </div>
      </div>
      <div class="model-actions">
        <button v-if="!modelEditing" class="edit-model-btn" type="button" @click="modelEditing = true">{{ modelConfigSaved ? '编辑' : '配置' }}</button>
        <button v-if="modelEditing" class="save-model-btn" :disabled="modelSaving" @click="handleSaveModel">
          {{ modelSaving ? '保存中...' : '保存' }}
        </button>
        <button v-if="modelEditing" class="cancel-model-btn" type="button" @click="modelEditing = false; loadModelConfig()">取消</button>
        <span v-if="modelMsg" class="feedback">{{ modelMsg }}</span>
      </div>
    </section>

    <!-- 联网搜索 -->
    <section class="setting-section">
      <h3>联网搜索</h3>
      <div class="setting-row toggle-row">
        <label>启用搜索</label>
        <input v-model="webSearchEnabledDraft" type="checkbox" />
      </div>
      <div class="setting-row">
        <label>代理地址</label>
        <input v-model="proxyUrlDraft" placeholder="http://127.0.0.1:7890" spellcheck="false" />
      </div>
      <div class="model-actions">
        <button class="save-model-btn" :disabled="webSearchSaving" @click="handleSaveWebSearch">
          {{ webSearchSaving ? '保存中...' : '保存' }}
        </button>
        <span v-if="webSearchMsg" class="feedback">{{ webSearchMsg }}</span>
      </div>
    </section>

    <!-- 系统提示 -->
    <section class="setting-section">
      <h3>系统提示</h3>
      <div class="input-row">
        <input
          v-model="newPromptContent"
          placeholder="输入系统指令"
          @keydown.enter="handleAddPrompt"
        />
        <button class="add-btn" :disabled="addingPrompt || !newPromptContent.trim()" @click="handleAddPrompt">
          {{ addingPrompt ? '...' : '添加' }}
        </button>
      </div>
      <p v-if="promptMsg" class="feedback">{{ promptMsg }}</p>
      <ul v-if="promptEntries.length" class="entry-list">
        <li v-for="entry in promptEntries" :key="entry.prompt_id" class="entry-row">
          <span class="entry-text">{{ entry.content }}</span>
          <button class="entry-del" title="删除" @click="handleDeletePrompt(entry.prompt_id)">&times;</button>
        </li>
      </ul>
    </section>

    <!-- 长期记忆 -->
    <section class="setting-section">
      <h3>长期记忆</h3>
      <div class="input-row">
        <input
          v-model="newMemoryContent"
          placeholder="输入记忆内容"
          @keydown.enter="handleAddMemory"
        />
        <button class="add-btn" :disabled="addingMemory || !newMemoryContent.trim()" @click="handleAddMemory">
          {{ addingMemory ? '...' : '添加' }}
        </button>
      </div>
      <p v-if="memoryMsg" class="feedback">{{ memoryMsg }}</p>
      <ul v-if="memories.length" class="entry-list">
        <li v-for="entry in memories" :key="entry.memory_id" class="entry-row">
          <span class="entry-text">{{ entry.content }}</span>
          <button class="entry-del" title="删除" @click="handleDeleteMemory(entry.memory_id)">&times;</button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  height: 100%;
  overflow-y: auto;
  padding: var(--space-16) var(--space-20);
  background:
    linear-gradient(180deg, var(--color-chrome-bg-top), var(--color-chrome-bg-bottom)),
    var(--color-chrome-bg-solid);
  font-size: 13px;
}

.setting-section {
  margin-bottom: var(--space-20);
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

.model-block h4 {
  margin: 0 0 var(--space-6);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
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
</style>
