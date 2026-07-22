<!--
  LLM settings section.

  Usage:
  Presents large and small model credentials. SettingsView owns loading,
  saving, and cancel behavior so model state remains centralized.
-->
<script setup lang="ts">
import type { SavedLLMConfig } from '@/api/settings'

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
  savedConfigs: SavedLLMConfig[]
}>()

defineEmits<{
  save: []
  cancel: []
  savePreset: [target: 'large' | 'small']
  importSavedConfig: [config: SavedLLMConfig, target: 'large' | 'small']
  deleteSavedConfig: [configId: string]
}>()
</script>

<template>
  <div class="setting-section">
    <h3>大模型</h3>
    <div class="model-block">
      <input v-model="largeModelName" placeholder="模型名称" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <input v-model="largeBaseUrl" placeholder="Base URL" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <div class="key-row">
        <input v-model="largeApiKey" :type="showLargeKey ? 'text' : 'password'" placeholder="API Key" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
        <button class="toggle-key" @click="showLargeKey = !showLargeKey">{{ showLargeKey ? '隐藏' : '显示' }}</button>
      </div>
    </div>
    <h3>小模型</h3>
    <p class="setting-hint">小模型留空时会自动使用大模型的模型名、Base URL 和 API Key。</p>
    <div class="model-block">
      <input v-model="smallModelName" placeholder="模型名称（留空继承大模型）" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
      <input v-model="smallBaseUrl" placeholder="Base URL（留空继承大模型）" spellcheck="false" :readonly="!modelEditing" :class="{ readonly: !modelEditing }" />
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
      <button v-if="modelEditing" class="edit-model-btn" type="button" @click="$emit('savePreset', 'large')">保存大模型配置</button>
      <button v-if="modelEditing" class="edit-model-btn" type="button" @click="$emit('savePreset', 'small')">保存小模型配置</button>
      <button v-if="modelEditing" class="cancel-model-btn" type="button" @click="$emit('cancel')">取消</button>
      <span v-if="modelMsg" class="feedback">{{ modelMsg }}</span>
    </div>
    <section class="saved-model-section">
      <h3>已保存的配置</h3>
      <p v-if="!savedConfigs.length" class="empty-hint">暂无已保存的模型配置。</p>
      <div v-else class="saved-model-grid">
        <article v-for="config in savedConfigs" :key="config.config_id" class="saved-model-card">
          <div class="saved-model-main">
            <strong>{{ config.label || config.model_name || '未命名配置' }}</strong>
            <span>{{ config.model_name || '未填写模型名称' }}</span>
            <small>{{ config.base_url || '未填写 Base URL' }}</small>
          </div>
          <div class="saved-model-actions">
            <button type="button" @click="$emit('importSavedConfig', config, 'large')">导入大模型</button>
            <button type="button" @click="$emit('importSavedConfig', config, 'small')">导入小模型</button>
            <button class="danger" type="button" @click="$emit('deleteSavedConfig', config.config_id)">删除</button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
