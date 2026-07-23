<!--
  图谱设置面板。

  Usage:
  允许用户配置知识图谱节点上限等参数。SettingsView 通过 model 同步草稿值。
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useSettingsStore } from '@/stores/settings'

const graphNodeLimitDraft = defineModel<number>('graphNodeLimitDraft', { required: true })

const settingsStore = useSettingsStore()
const saving = ref(false)
const saveMsg = ref('')

const settingsStoreProfileGraphNodeLimit = computed(() => {
  return settingsStore.profile.graphNodeLimit ?? 2000
})

function showMessage(text: string, duration = 2000) {
  saveMsg.value = text
  setTimeout(() => { saveMsg.value = '' }, duration)
}

watch(
  settingsStoreProfileGraphNodeLimit,
  (value) => {
    graphNodeLimitDraft.value = value
  },
)

async function handleSave() {
  const limit = Number(graphNodeLimitDraft.value)
  if (!Number.isFinite(limit) || limit < 50 || limit > 10000) {
    showMessage('节点上限需在 50 ~ 10000 之间')
    return
  }
  saving.value = true
  saveMsg.value = ''
  try {
    await settingsStore.saveGraphSettings({ graphNodeLimit: Math.round(limit) })
    showMessage('已保存')
  } catch {
    showMessage('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="setting-section">
    <h3>图谱配置</h3>
    <div class="setting-row">
      <label>节点上限</label>
      <input
        v-model.number="graphNodeLimitDraft"
        type="number"
        min="50"
        max="10000"
        step="100"
        placeholder="2000"
        spellcheck="false"
        @keyup.enter="handleSave"
        @blur="handleSave"
      />
    </div>
    <div class="setting-hint">
      知识图谱一次最多返回的节点数。增加此值可显示更多节点，但可能影响渲染性能。
    </div>
    <div class="model-actions">
      <span v-if="saving" class="feedback">保存中...</span>
      <span v-if="saveMsg" class="feedback">{{ saveMsg }}</span>
    </div>
  </div>
</template>
