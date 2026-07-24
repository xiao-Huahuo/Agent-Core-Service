<!--
  Web search settings section.

  Usage:
  Edits the search enable switch, proxy URL, and max results. SettingsView owns
  validation and persistence through the settings API.
-->
<script setup lang="ts">
const proxyUrlDraft = defineModel<string>('proxyUrlDraft', { required: true })
const webSearchEnabledDraft = defineModel<boolean>('webSearchEnabledDraft', { required: true })
const webSearchMaxResultsDraft = defineModel<number>('webSearchMaxResultsDraft', { required: true })

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
      <input v-model="webSearchEnabledDraft" type="checkbox" @change="$emit('save')" />
    </div>
    <div class="setting-row">
      <label>代理地址</label>
      <input v-model="proxyUrlDraft" placeholder="http://127.0.0.1:7890" spellcheck="false" @blur="$emit('save')" />
    </div>
    <div class="setting-row">
      <label>每次最大结果数</label>
      <input
        v-model.number="webSearchMaxResultsDraft"
        type="number"
        min="1"
        max="50"
        placeholder="10"
        class="num-input"
        @change="$emit('save')"
      />
    </div>
    <div class="model-actions">
      <span v-if="webSearchSaving" class="feedback">保存中...</span>
      <span v-if="webSearchMsg" class="feedback">{{ webSearchMsg }}</span>
    </div>
  </div>
</template>

<style scoped>
.num-input {
  width: 64px;
  flex: none;
}
</style>