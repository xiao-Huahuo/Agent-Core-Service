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
  </div>
</template>
