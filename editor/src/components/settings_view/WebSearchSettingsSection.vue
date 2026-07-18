<!--
  Web search settings section.

  Usage:
  Edits the search enable switch and proxy URL draft. SettingsView owns
  validation and persistence through the settings API.
-->
<script setup lang="ts">
const proxyUrlDraft = defineModel<string>('proxyUrlDraft', { required: true })
const webSearchEnabledDraft = defineModel<boolean>('webSearchEnabledDraft', { required: true })

defineProps<{
  webSearchSaving: boolean
  webSearchMsg: string
}>()

defineEmits<{
  save: []
}>()
</script>

<template>
  <div class="setting-section">
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
      <button class="save-model-btn" :disabled="webSearchSaving" @click="$emit('save')">
        {{ webSearchSaving ? '保存中...' : '保存' }}
      </button>
      <span v-if="webSearchMsg" class="feedback">{{ webSearchMsg }}</span>
    </div>
  </div>
</template>
