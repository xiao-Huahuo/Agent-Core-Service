<!--
  Basic settings section.

  Usage:
  Edits knowledge library metadata and ingestion switches. The parent owns
  persistence and side effects.
-->
<script setup lang="ts">
const libraryNameDraft = defineModel<string>('libraryNameDraft', { required: true })
const knowledgeDirDraft = defineModel<string>('knowledgeDirDraft', { required: true })
const watchEnabledDraft = defineModel<boolean>('watchEnabledDraft', { required: true })
const autoIngestOnUploadDraft = defineModel<boolean>('autoIngestOnUploadDraft', { required: true })
const ocrEnabledDraft = defineModel<boolean>('ocrEnabledDraft', { required: true })
const knowledgeIgnorePatternsDraft = defineModel<string>('knowledgeIgnorePatternsDraft', { required: true })

defineProps<{
  hasChanges: boolean
  saving: boolean
  saveMessage: string
  saveError: string
}>()

defineEmits<{
  save: []
  logout: []
}>()
</script>

<template>
  <div class="setting-section">
    <h3>知识库</h3>
    <div class="setting-row">
      <label>库名称</label>
      <input v-model="libraryNameDraft" spellcheck="false" @blur="$emit('save')" />
    </div>
    <div class="setting-row">
      <label>知识目录</label>
      <input v-model="knowledgeDirDraft" spellcheck="false" @blur="$emit('save')" />
    </div>

    <div class="setting-row toggle-row">
      <label>文件监听</label>
      <input v-model="watchEnabledDraft" type="checkbox" @change="$emit('save')" />
    </div>
    <div class="setting-row toggle-row">
      <label>自动灌库</label>
      <input v-model="autoIngestOnUploadDraft" type="checkbox" @change="$emit('save')" />
      <span class="hint-text">关闭时上传只进入文件树,点击 header 刷新或文件按钮才灌库</span>
    </div>
    <div class="setting-row toggle-row">
      <label>OCR</label>
      <input v-model="ocrEnabledDraft" type="checkbox" @change="$emit('save')" />
      <span class="hint-text">开启后需重启;重启时会检查并预热 PaddleOCR 中英文模型</span>
    </div>
    <div class="setting-row ignore-row">
      <label>屏蔽区</label>
      <textarea
        v-model="knowledgeIgnorePatternsDraft"
        spellcheck="false"
        placeholder="# gitignore-like&#10;private/&#10;*.tmp&#10;!private/keep.md"
        @blur="$emit('save')"
      ></textarea>
    </div>
    <p class="setting-hint">被屏蔽的文件不会入库;已入库文件会在下次 Ingest 或单文件灌库时出库。</p>
    <div class="model-actions">
      <span v-if="saving" class="feedback">保存中...</span>
      <span v-if="saveMessage" class="feedback">{{ saveMessage }}</span>
      <span v-if="saveError" class="feedback error">{{ saveError }}</span>
    </div>
    <section class="logout-section">
      <div>
        <h3>当前身份</h3>
        <p class="setting-hint">退出后会回到 user_id 输入入口,本地知识库和用户配置不会被删除。</p>
      </div>
      <button class="logout-button" type="button" @click="$emit('logout')">退出登录</button>
    </section>
  </div>
</template>

<style scoped>
.logout-section {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-12);
  margin-top: var(--space-12);
  padding-top: var(--space-14);
  border-top: 1px solid var(--color-border);
}

.logout-section h3 {
  margin: 0 0 var(--space-4);
}

.logout-button {
  height: 32px;
  padding: 0 var(--space-12);
  border: 1px solid color-mix(in srgb, var(--color-danger) 58%, var(--color-border));
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-danger);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.logout-button:hover {
  border-color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 10%, transparent);
}

@media (max-width: 560px) {
  .logout-section {
    grid-template-columns: 1fr;
  }

  .logout-button {
    justify-self: start;
  }
}
</style>
