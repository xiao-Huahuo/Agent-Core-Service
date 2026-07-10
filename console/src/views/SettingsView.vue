<script setup>
import { ref, onMounted } from 'vue'
import { useUserId } from '@/composable/useUserId'
import {
  fetchSystemPrompt, addSystemPromptEntry, deleteSystemPromptEntry,
  fetchMemories, addMemory, deleteMemory,
} from '@/api/settings'

const { userId } = useUserId()

const promptEntries = ref([])
const newPromptContent = ref('')
const addingPrompt = ref(false)
const promptMsg = ref('')

const memories = ref([])
const newMemoryContent = ref('')
const adding = ref(false)
const memMsg = ref('')

function showMsg(refObj, text, duration = 2000) {
  refObj.value = text
  setTimeout(() => { refObj.value = '' }, duration)
}

async function load() {
  if (!userId.value) return
  await Promise.all([loadPrompts(), loadMemories()])
}

async function loadPrompts() {
  try {
    const res = await fetchSystemPrompt(userId.value)
    promptEntries.value = res.entries || []
  } catch { /* ignore */ }
}

async function loadMemories() {
  try {
    const data = await fetchMemories(userId.value)
    memories.value = data || []
  } catch { /* ignore */ }
}

async function handleAddPrompt() {
  const content = newPromptContent.value.trim()
  if (!content || !userId.value) return
  addingPrompt.value = true
  try {
    await addSystemPromptEntry(userId.value, content)
    newPromptContent.value = ''
    await loadPrompts()
    showMsg(promptMsg, '✓ 已添加')
  } catch {
    showMsg(promptMsg, '✗ 添加失败')
  } finally {
    addingPrompt.value = false
  }
}

async function handleDeletePrompt(id) {
  try {
    await deleteSystemPromptEntry(id)
    await loadPrompts()
    showMsg(promptMsg, '✓ 已删除')
  } catch {
    showMsg(promptMsg, '✗ 删除失败')
  }
}

async function handleAddMemory() {
  const content = newMemoryContent.value.trim()
  if (!content || !userId.value) return
  adding.value = true
  try {
    await addMemory(userId.value, content)
    newMemoryContent.value = ''
    await loadMemories()
    showMsg(memMsg, '✓ 已添加')
  } catch {
    showMsg(memMsg, '✗ 添加失败')
  } finally {
    adding.value = false
  }
}

async function handleDeleteMemory(id) {
  try {
    await deleteMemory(id)
    await loadMemories()
    showMsg(memMsg, '✓ 已删除')
  } catch {
    showMsg(memMsg, '✗ 删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <div class="settings-panel">
      <!-- 系统提示词条目 -->
      <section class="settings-section">
        <div class="section-header">
          <h3 class="section-title">$ system_prompts</h3>
          <span class="section-hint">自定义系统提示词条目，每次对话自动全部加载</span>
        </div>
        <div class="input-row">
          <input
            v-model="newPromptContent"
            class="text-input"
            placeholder="输入一条系统指令..."
            @keydown.enter="handleAddPrompt"
          />
          <button class="save-btn" :disabled="addingPrompt || !newPromptContent.trim()" @click="handleAddPrompt">
            {{ addingPrompt ? '...' : '添加' }}
          </button>
        </div>
        <span v-if="promptMsg" class="feedback">{{ promptMsg }}</span>
        <ul v-if="promptEntries.length" class="item-list">
          <li v-for="e in promptEntries" :key="e.prompt_id" class="item-row">
            <span class="item-text">{{ e.content }}</span>
            <button class="item-del" @click="handleDeletePrompt(e.prompt_id)">×</button>
          </li>
        </ul>
        <p v-else class="empty-hint">$ no custom prompts</p>
      </section>

      <!-- 长期记忆 -->
      <section class="settings-section">
        <div class="section-header">
          <h3 class="section-title">$ longterm_memories</h3>
          <span class="section-hint">自定义知识注入向量库，持久化存储</span>
        </div>
        <div class="input-row">
          <input
            v-model="newMemoryContent"
            class="text-input"
            placeholder="输入要记住的知识..."
            @keydown.enter="handleAddMemory"
          />
          <button class="save-btn" :disabled="adding || !newMemoryContent.trim()" @click="handleAddMemory">
            {{ adding ? '...' : '添加' }}
          </button>
        </div>
        <span v-if="memMsg" class="feedback">{{ memMsg }}</span>
        <ul v-if="memories.length" class="item-list">
          <li v-for="m in memories" :key="m.memory_id" class="item-row">
            <span class="item-text">{{ m.content }}</span>
            <button class="item-del" @click="handleDeleteMemory(m.memory_id)">×</button>
          </li>
        </ul>
        <p v-else class="empty-hint">$ no custom memories</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-24);
  display: flex;
  justify-content: center;
}

.settings-panel {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: var(--space-24);
}

.settings-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-16);
}

.section-header {
  margin-bottom: var(--space-10);
}

.section-title {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-4) 0;
}

.section-hint {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.input-row {
  display: flex;
  gap: var(--space-8);
}

.text-input {
  flex: 1;
  padding: var(--space-8) var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-muted);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  outline: none;
  transition: border-color var(--transition-fast);
}

.text-input:focus {
  border-color: var(--color-accent);
}

.save-btn {
  padding: var(--space-6) var(--space-14);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.save-btn:hover:not(:disabled) {
  color: var(--color-text-primary);
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
}

.save-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.feedback {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-accent);
  margin-top: var(--space-6);
}

.item-list {
  list-style: none;
  margin: var(--space-10) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.item-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-muted);
}

.item-text {
  flex: 1;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-del {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.item-del:hover {
  color: rgb(255, 95, 95);
  border-color: rgba(255, 95, 95, 0.4);
  background: rgba(255, 95, 95, 0.08);
}

.empty-hint {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin: var(--space-10) 0 0;
}
</style>
