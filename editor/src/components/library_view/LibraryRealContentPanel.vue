<!--
  Library real-content panel.

  Usage:
  Renders the source content of a library book in the edit dialog. It keeps
  metadata editing in LibraryItemDialog while providing type-specific access
  for files, images, URLs, plain text, and code.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { buildApiUrl } from '@/api/client'
import { readKnowledgeFile } from '@/api/knowledge'
import CompactCodeInput from '@/components/common/CompactCodeInput.vue'
import IcIcon from '@/components/common/IcIcon.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { LibraryItem } from '@/types/knowledge'

defineOptions({ name: 'LibraryRealContentPanel' })

type RealContentKind = 'file' | 'image' | 'web_url' | 'text' | 'code'

const CODE_MIME_PATTERN = /javascript|typescript|python|java|c\\+\\+|csharp|rust|shell|css|html|sql|php|ruby|golang|yaml|json|xml/i
const CODE_EXTENSION_PATTERN = /\\.(?:asm|c|cc|cpp|cxx|cs|css|go|h|hpp|html?|java|js|jsx|json|kt|kts|less|php|ps1|py|rb|rs|scss|sh|sql|swift|ts|tsx|vue|xml|yaml|yml)$/i
const IMAGE_EXTENSION_PATTERN = /\\.(?:avif|bmp|gif|jpe?g|png|svg|webp)$/i
const TEXT_EXTENSION_PATTERN = /\\.(?:csv|log|md|markdown|rst|text|tsv|txt)$/i

const props = defineProps<{
  item: LibraryItem
  userId: string
}>()

const emit = defineEmits<{
  openFile: [item: LibraryItem]
  openUrl: [url: string]
  contentLoaded: [content: string]
  contentChange: [content: string]
}>()

const content = ref('')
const loading = ref(false)
const loadError = ref('')
let loadSequence = 0
let suppressContentChange = false

const sourceName = computed(() => props.item.source_name || props.item.source_path || props.item.display_title)
const sourceExtension = computed(() => {
  const value = props.item.source_path || sourceName.value
  return (value.split('?')[0] ?? value).toLowerCase()
})
const sourceKind = computed<RealContentKind>(() => {
  if (props.item.content_type === 'web_url') return 'web_url'
  if (props.item.source_mime.startsWith('image/') || IMAGE_EXTENSION_PATTERN.test(sourceExtension.value)) return 'image'
  if (CODE_MIME_PATTERN.test(props.item.source_mime) || CODE_EXTENSION_PATTERN.test(sourceExtension.value)) return 'code'
  if (props.item.source_mime.startsWith('text/') || TEXT_EXTENSION_PATTERN.test(sourceExtension.value)) return 'text'
  return 'file'
})
const imageUrl = computed(() => {
  if (sourceKind.value !== 'image' || !props.item.source_path) return ''
  return buildApiUrl('/knowledge/files/raw', {
    user_id: props.item.user_id || props.userId,
    path: props.item.source_path,
  })
})
const fileIcon = computed(() => materialFileIconForNode({
  name: sourceName.value,
  path: props.item.source_path || sourceName.value,
  isDir: false,
}))
const sourceKindLabel = computed(() => {
  if (sourceKind.value === 'file') return '真实文件'
  if (sourceKind.value === 'image') return '图片'
  if (sourceKind.value === 'web_url') return '网页 URL'
  if (sourceKind.value === 'text') return '纯文本'
  return '代码'
})

async function loadTextContent() {
  const sequence = ++loadSequence
  suppressContentChange = true
  content.value = ''
  loadError.value = ''
  if (!['text', 'code'].includes(sourceKind.value) || !props.item.source_path || !props.userId) {
    suppressContentChange = false
    return
  }
  loading.value = true
  try {
    const response = await readKnowledgeFile(props.userId, props.item.source_path)
    if (sequence === loadSequence) {
      suppressContentChange = true
      content.value = response.content
      await nextTick()
      suppressContentChange = false
      emit('contentLoaded', response.content)
    }
  } catch (error) {
    if (sequence === loadSequence) {
      loadError.value = error instanceof Error ? error.message : '真实内容读取失败'
    }
  } finally {
    if (sequence === loadSequence) {
      suppressContentChange = false
      loading.value = false
    }
  }
}

watch(content, (value) => {
  if (!suppressContentChange && ['text', 'code'].includes(sourceKind.value)) {
    emit('contentChange', value)
  }
})

watch(
  [() => props.item.item_id, () => props.item.source_path, () => props.item.source_mime, sourceKind],
  () => { void loadTextContent() },
  { immediate: true },
)
</script>

<template>
  <section class="real-content-panel">
    <header class="real-content-head">
      <span>元文件</span>
      <small>{{ sourceKindLabel }}</small>
    </header>

    <div v-if="sourceKind === 'file'" class="real-content-body file-content">
      <button
        class="source-file-tile"
        type="button"
        :disabled="!item.source_exists || !item.source_path"
        :title="item.source_exists ? '在编辑区打开真实文件' : '真实文件已缺失'"
        @click="emit('openFile', item)"
      >
        <img class="source-file-icon" :src="fileIcon.src" :alt="fileIcon.alt" />
        <strong>{{ sourceName }}</strong>
        <small>{{ item.source_exists ? '点击在编辑区打开' : '真实文件已缺失' }}</small>
      </button>
    </div>

    <div v-else-if="sourceKind === 'image'" class="real-content-body image-content">
      <img
        v-if="imageUrl"
        class="source-image"
        :src="imageUrl"
        :alt="sourceName"
      />
      <span v-else class="real-content-empty">暂无可展示的图片</span>
    </div>

    <div v-else-if="sourceKind === 'web_url'" class="real-content-body url-content">
      <div class="source-url-row">
        <div class="source-url-field" :title="item.source_url">
          <IcIcon name="link" :size="15" />
          <span>{{ item.source_url || '未设置 URL' }}</span>
        </div>
        <button
          class="source-url-open"
          type="button"
          :disabled="!item.source_url"
          title="在右侧浏览器打开"
          aria-label="在右侧浏览器打开"
          @click="emit('openUrl', item.source_url)"
        >
          <IcIcon name="open-in-new" :size="15" />
        </button>
      </div>
    </div>

    <div v-else-if="sourceKind === 'code'" class="real-content-body code-content">
      <div v-if="loading" class="real-content-empty">正在读取代码</div>
      <div v-else-if="loadError" class="real-content-empty">{{ loadError }}</div>
      <div v-else class="real-code-box">
        <CompactCodeInput
          v-model="content"
          label="代码"
          placeholder="暂无代码内容"
        />
      </div>
    </div>

    <div v-else class="real-content-body text-content">
      <div v-if="loading" class="real-content-empty">正在读取文本</div>
      <div v-else-if="loadError" class="real-content-empty">{{ loadError }}</div>
      <label v-else class="real-text-field">
        <span>纯文本</span>
        <textarea v-model="content" spellcheck="false" aria-label="纯文本内容"></textarea>
      </label>
    </div>
  </section>
</template>

<style scoped>
.real-content-panel {
  display: flex;
  min-width: 0;
  min-height: 320px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-surface-raised);
}

.real-content-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  font-weight: 700;
}

.real-content-head small {
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 400;
}

.real-content-body {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  padding: 14px;
}

.file-content,
.image-content,
.url-content {
  place-items: center;
}

.source-file-tile {
  display: grid;
  place-items: center;
  gap: 8px;
  width: min(220px, 100%);
  min-height: 210px;
  border: 0;
  border-radius: 18px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 18px;
  cursor: pointer;
}

.source-file-tile:hover:not(:disabled) {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.source-file-tile:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.source-file-tile strong,
.source-file-tile small {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-file-tile small {
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 400;
}

.source-file-icon {
  width: 96px;
  height: 96px;
  object-fit: contain;
}

.source-image {
  display: block;
  max-width: 100%;
  max-height: 300px;
  object-fit: contain;
  border-radius: 18px;
}

.source-url-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.source-url-field {
  display: flex;
  align-items: center;
  min-width: 0;
  min-height: 38px;
  flex: 1;
  gap: 7px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  padding: 0 12px;
}

.source-url-field span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-url-open {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  cursor: pointer;
}

.source-url-open:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.source-url-open:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.real-code-box {
  min-width: 0;
  min-height: 240px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: var(--color-canvas);
}

.real-code-box :deep(.compact-code-input) {
  height: 100%;
}

.real-text-field {
  display: flex;
  min-width: 0;
  min-height: 240px;
  flex-direction: column;
  gap: 7px;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.real-text-field textarea {
  min-height: 0;
  flex: 1;
  resize: none;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 12px 14px;
  font-family: var(--font-text);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
}

.real-content-empty {
  align-self: center;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}
</style>
