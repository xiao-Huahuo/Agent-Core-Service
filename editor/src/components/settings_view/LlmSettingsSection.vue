<!--
  LLM settings section.

  Usage:
  Presents large and small model credentials. SettingsView owns loading,
  saving, and cancel behavior so model state remains centralized.
-->
<script setup lang="ts">
const largeModelName = defineModel<string>('largeModelName', { required: true })
const largeBaseUrl = defineModel<string>('largeBaseUrl', { required: true })
const largeApiKey = defineModel<string>('largeApiKey', { required: true })
const smallModelName = defineModel<string>('smallModelName', { required: true })
const smallBaseUrl = defineModel<string>('smallBaseUrl', { required: true })
const smallApiKey = defineModel<string>('smallApiKey', { required: true })
const showLargeKey = defineModel<boolean>('showLargeKey', { required: true })
const showSmallKey = defineModel<boolean>('showSmallKey', { required: true })
const modelEditing = defineModel<boolean>('modelEditing', { required: true })

defineProps<{
  modelConfigSaved: boolean
  modelSaving: boolean
  modelMsg: string
}>()

defineEmits<{
  save: []
  cancel: []
}>()
</script>

<template>
  <div class="setting-section">
    <h3>大模型</h3>
    <div class="model-block">
      <input v-model="largeModelName" placeholder="deepseek-v4-flash" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <input v-model="largeBaseUrl" placeholder="https://api.deepseek.com" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <div class="key-row">
        <input v-model="largeApiKey" :type="showLargeKey ? 'text' : 'password'" placeholder="API Key" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <button class="toggle-key" @click="showLargeKey = !showLargeKey">{{ showLargeKey ? '隐藏' : '显示' }}</button>
      </div>
    </div>
    <h3>小模型</h3>
    <div class="model-block">
      <input v-model="smallModelName" placeholder="moonshot-v1-8k" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <input v-model="smallBaseUrl" placeholder="https://api.moonshot.cn/v1" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <div class="key-row">
        <input v-model="smallApiKey" :type="showSmallKey ? 'text' : 'password'" placeholder="API Key" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <button class="toggle-key" @click="showSmallKey = !showSmallKey">{{ showSmallKey ? '隐藏' : '显示' }}</button>
      </div>
    </div>
    <div class="model-actions">
      <button v-if="!modelEditing" class="edit-model-btn" type="button" @click="modelEditing = true">{{ modelConfigSaved ? '编辑' : '配置' }}</button>
      <button v-if="modelEditing" class="save-model-btn" :disabled="modelSaving" @click="$emit('save')">
        {{ modelSaving ? '保存中...' : '保存' }}
      </button>
      <button v-if="modelEditing" class="cancel-model-btn" type="button" @click="$emit('cancel')">取消</button>
      <span v-if="modelMsg" class="feedback">{{ modelMsg }}</span>
    </div>
  </div>
</template>
