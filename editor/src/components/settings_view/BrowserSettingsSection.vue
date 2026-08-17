<!--
  Embedded browser settings section.

  Usage:
  SettingsView owns persistence; this component edits the browser-only proxy
  override and home page while explaining the networking-proxy fallback.
-->
<script setup lang="ts">
defineOptions({ name: 'BrowserSettingsSection' })

const browserProxyUrlDraft = defineModel<string>('browserProxyUrlDraft', { required: true })
const browserHomeUrlDraft = defineModel<string>('browserHomeUrlDraft', { required: true })

defineProps<{
  inheritedProxyUrl: string
  saving: boolean
  statusMessage: string
}>()

defineEmits<{ save: [] }>()
</script>

<template>
  <section class="setting-section browser-settings-section">
    <h3>内置浏览器</h3>
    <div class="setting-row">
      <label for="browser-home-url">主页</label>
      <input
        id="browser-home-url"
        v-model.trim="browserHomeUrlDraft"
        type="url"
        placeholder="https://www.google.com"
      />
    </div>
    <div class="setting-row">
      <label for="browser-proxy-url">代理</label>
      <input
        id="browser-proxy-url"
        v-model.trim="browserProxyUrlDraft"
        type="text"
        placeholder="留空则复用联网搜索代理"
        spellcheck="false"
      />
    </div>
    <p class="setting-hint browser-proxy-hint">
      当前继承值：{{ inheritedProxyUrl || '直连' }}。支持 HTTP、HTTPS 与 SOCKS 代理地址。
    </p>
    <div class="browser-settings-actions">
      <button class="save-model-btn" type="button" :disabled="saving" @click="$emit('save')">
        {{ saving ? '保存中…' : '保存浏览器配置' }}
      </button>
      <span v-if="statusMessage" class="feedback">{{ statusMessage }}</span>
    </div>
  </section>
</template>

<style scoped>
.browser-settings-section {
  max-width: 720px;
}

.browser-proxy-hint {
  overflow-wrap: anywhere;
}

.browser-settings-actions {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  margin-left: 82px;
}
</style>
