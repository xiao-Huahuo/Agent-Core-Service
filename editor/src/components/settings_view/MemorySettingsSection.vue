<!--
  Memory and prompt settings section.

  Usage:
  Displays system prompt entries and custom memory entries. SettingsView owns
  add/delete handlers and API synchronization.
-->
<script setup lang="ts">
import type { MemoryEntry, SystemPromptEntry } from '@/api/settings'

const newPromptContent = defineModel<string>('newPromptContent', { required: true })
const newMemoryContent = defineModel<string>('newMemoryContent', { required: true })

defineProps<{
  promptEntries: SystemPromptEntry[]
  addingPrompt: boolean
  promptMsg: string
  memories: MemoryEntry[]
  addingMemory: boolean
  memoryMsg: string
}>()

defineEmits<{
  addPrompt: []
  deletePrompt: [promptId: string]
  addMemory: []
  deleteMemory: [memoryId: string]
}>()
</script>

<template>
  <div class="setting-section">
    <h3>系统提示</h3>
    <div class="input-row">
      <input
        v-model="newPromptContent"
        placeholder="输入系统指令"
        @keydown.enter="$emit('addPrompt')"
      />
      <button class="add-btn" :disabled="addingPrompt || !newPromptContent.trim()" @click="$emit('addPrompt')">
        {{ addingPrompt ? '...' : '添加' }}
      </button>
    </div>
    <p v-if="promptMsg" class="feedback">{{ promptMsg }}</p>
    <ul v-if="promptEntries.length" class="entry-list">
      <li v-for="entry in promptEntries" :key="entry.prompt_id" class="entry-row">
        <span class="entry-text">{{ entry.content }}</span>
        <button class="entry-del" title="删除" @click="$emit('deletePrompt', entry.prompt_id)">&times;</button>
      </li>
    </ul>

    <h3 style="margin-top: 20px">长期记忆</h3>
    <div class="input-row">
      <input
        v-model="newMemoryContent"
        placeholder="输入记忆内容"
        @keydown.enter="$emit('addMemory')"
      />
      <button class="add-btn" :disabled="addingMemory || !newMemoryContent.trim()" @click="$emit('addMemory')">
        {{ addingMemory ? '...' : '添加' }}
      </button>
    </div>
    <p v-if="memoryMsg" class="feedback">{{ memoryMsg }}</p>
    <ul v-if="memories.length" class="entry-list">
      <li v-for="entry in memories" :key="entry.memory_id" class="entry-row">
        <span class="entry-text">{{ entry.content }}</span>
        <button class="entry-del" title="删除" @click="$emit('deleteMemory', entry.memory_id)">&times;</button>
      </li>
    </ul>
  </div>
</template>
