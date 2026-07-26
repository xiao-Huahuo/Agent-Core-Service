<!--
  Library create dialog.

  Usage:
  Creates a virtual library book or collection. Book creation collects virtual
  metadata, an optional cover image key, and one selected source: uploaded file,
  direct text content, or a web URL.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { FileText, Globe, ImagePlus, Save, UploadCloud, X, XCircle } from 'lucide-vue-next'

import { uploadLibraryCover } from '@/api/library'
import type { LibraryItem } from '@/types/knowledge'

type CreateMode = 'book' | 'collection'
type BookSourceMode = 'file' | 'text' | 'url'

const props = defineProps<{
  open: boolean
  mode: CreateMode
  userId: string
}>()

const emit = defineEmits<{
  close: []
  create: [payload: {
    title: string
    description: string
    tags: string[]
    cover_mode: LibraryItem['cover_mode']
    cover_asset_id: string
    file: File | null
    source_mode: BookSourceMode
    text_content: string
    source_url: string
  }]
}>()

const title = ref('')
const description = ref('')
const tags = ref<string[]>([])
const tagDraft = ref('')
const coverAssetId = ref('')
const coverPreviewUrl = ref('')
const realFile = ref<File | null>(null)
const sourceMode = ref<BookSourceMode>('file')
const textContent = ref('')
const sourceUrl = ref('')
const coverUploading = ref(false)
const coverDragActive = ref(false)
const dragActive = ref(false)
const coverInput = ref<HTMLInputElement | null>(null)
const realFileInput = ref<HTMLInputElement | null>(null)

const isBook = computed(() => props.mode === 'book')
const heading = computed(() => (isBook.value ? '新增文件' : '新增集锦'))
const coverMode = computed<LibraryItem['cover_mode']>(() => (coverAssetId.value ? 'image' : 'title'))

watch(
  () => props.open,
  (open) => {
    if (!open) return
    title.value = ''
    description.value = ''
    tags.value = []
    tagDraft.value = ''
    coverAssetId.value = ''
    coverPreviewUrl.value = ''
    realFile.value = null
    sourceMode.value = 'file'
    textContent.value = ''
    sourceUrl.value = ''
    coverDragActive.value = false
    dragActive.value = false
  },
)

function setSourceMode(mode: BookSourceMode) {
  sourceMode.value = mode
  dragActive.value = false
}

function addTag(rawValue = tagDraft.value) {
  const name = rawValue.trim()
  if (!name) return
  if (!tags.value.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
    tags.value = [...tags.value, name]
  }
  tagDraft.value = ''
}

function handleTagKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ',') return
  event.preventDefault()
  addTag()
}

function removeTag(name: string) {
  tags.value = tags.value.filter((tag) => tag !== name)
}

function selectRealFile(event: Event) {
  const input = event.target as HTMLInputElement
  realFile.value = input.files?.[0] ?? null
}

function dropRealFile(event: DragEvent) {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    realFile.value = file
  }
}

async function uploadCover(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.userId) return
  await uploadCoverFile(file)
  input.value = ''
}

async function dropCover(event: DragEvent) {
  coverDragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file || !props.userId) return
  await uploadCoverFile(file)
}

async function uploadCoverFile(file: File) {
  coverUploading.value = true
  try {
    const response = await uploadLibraryCover(props.userId, file)
    coverAssetId.value = response.asset?.asset_id ?? ''
    coverPreviewUrl.value = response.asset?.url ?? ''
  } finally {
    coverUploading.value = false
  }
}

function submit() {
  addTag()
  emit('create', {
    title: title.value.trim(),
    description: description.value.trim(),
    tags: tags.value,
    cover_mode: coverMode.value,
    cover_asset_id: coverAssetId.value,
    file: realFile.value,
    source_mode: sourceMode.value,
    text_content: textContent.value,
    source_url: sourceUrl.value.trim(),
  })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-backdrop" @click.self="emit('close')">
      <section class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-head">
          <h2>{{ heading }}</h2>
          <button class="icon-btn" type="button" title="关闭" @click="emit('close')">
            <X :size="16" />
          </button>
        </header>

        <section class="upper-grid">
          <div class="metadata-zone">
            <label class="field">
              <span>标题</span>
              <input v-model="title" type="text" spellcheck="false" placeholder="留空使用默认名称" />
            </label>
            <label class="field">
              <span>描述</span>
              <textarea v-model="description" rows="5" placeholder="用于搜索和归纳说明" />
            </label>
            <div class="field">
              <span>标签</span>
              <div class="tag-input-wrap">
                <input
                  v-model="tagDraft"
                  type="text"
                  spellcheck="false"
                  placeholder="输入标签后回车"
                  @blur="addTag()"
                  @keydown="handleTagKeydown"
                />
              </div>
              <div v-if="tags.length" class="tag-list">
                <button
                  v-for="tag in tags"
                  :key="tag"
                  class="tag-pill"
                  type="button"
                  :title="`移除 ${tag}`"
                  @click="removeTag(tag)"
                >
                  <span>{{ tag }}</span>
                  <XCircle :size="13" />
                </button>
              </div>
            </div>
          </div>

          <div class="cover-zone">
            <input ref="coverInput" class="hidden-input" type="file" accept="image/*" @change="uploadCover" />
            <button
              class="cover-drop"
              :class="{ active: coverDragActive }"
              type="button"
              :disabled="coverUploading"
              @click="coverInput?.click()"
              @dragenter.prevent="coverDragActive = true"
              @dragover.prevent="coverDragActive = true"
              @dragleave.prevent="coverDragActive = false"
              @drop.prevent="dropCover"
            >
              <img v-if="coverPreviewUrl" class="cover-preview" :src="coverPreviewUrl" alt="" />
              <template v-else>
                <ImagePlus :size="30" />
                <span>{{ coverUploading ? '上传中' : '点击或拖拽上传封面' }}</span>
              </template>
            </button>
          </div>
        </section>

        <section v-if="isBook && sourceMode === 'file'" class="file-zone">
          <input ref="realFileInput" class="hidden-input" type="file" @change="selectRealFile" />
          <button
            class="file-drop"
            :class="{ active: dragActive }"
            type="button"
            @click="realFileInput?.click()"
            @dragenter.prevent="dragActive = true"
            @dragover.prevent="dragActive = true"
            @dragleave.prevent="dragActive = false"
            @drop.prevent="dropRealFile"
          >
            <UploadCloud :size="24" />
            <span>{{ realFile?.name || '拖拽真实文件到这里' }}</span>
          </button>
        </section>

        <section v-else-if="isBook && sourceMode === 'text'" class="text-zone">
          <label class="text-content-field">
            <span>文本内容</span>
            <textarea v-model="textContent" rows="8" spellcheck="false" placeholder="输入后会保存为 Markdown 文件" />
          </label>
        </section>

        <section v-else-if="isBook && sourceMode === 'url'" class="url-zone">
          <label class="url-input-wrap">
            <Globe :size="15" />
            <input v-model="sourceUrl" type="url" spellcheck="false" placeholder="URL" />
          </label>
        </section>

        <footer class="dialog-actions">
          <div v-if="isBook" class="source-mode-actions" aria-label="文件来源">
            <button
              class="source-mode-btn"
              :class="{ active: sourceMode === 'text' }"
              type="button"
              title="文本"
              aria-label="文本"
              @click="setSourceMode(sourceMode === 'text' ? 'file' : 'text')"
            >
              <FileText :size="16" />
            </button>
            <button
              class="source-mode-btn"
              :class="{ active: sourceMode === 'url' }"
              type="button"
              title="网页"
              aria-label="网页"
              @click="setSourceMode(sourceMode === 'url' ? 'file' : 'url')"
            >
              <Globe :size="16" />
            </button>
          </div>
          <div class="submit-actions">
            <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
            <button class="primary-btn" type="button" @click="submit">
              <Save :size="14" />
              创建
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.42);
}

.dialog-panel {
  width: min(760px, calc(100vw - 32px));
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

.dialog-head h2 {
  margin: 0;
  font-size: calc(15px * var(--font-scale));
}

.upper-grid {
  display: grid;
  grid-template-columns: 5fr 3fr;
  gap: 14px;
  padding: 16px 16px 0;
}

.metadata-zone {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.field {
  display: grid;
  gap: 7px;
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text-secondary);
}

.field input[type="text"] {
  width: 100%;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 0 14px;
  font-size: calc(13px * var(--font-scale));
  outline: none;
}

.field input[type="text"]:focus {
  border-color: var(--color-primary);
}

.field textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 10px 14px;
  resize: vertical;
  font-size: calc(13px * var(--font-scale));
  outline: none;
}

.field textarea:focus {
  border-color: var(--color-primary);
}

.tag-input-wrap {
  display: flex;
  align-items: center;
  min-height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  padding: 0 14px;
}

.tag-input-wrap input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  border-radius: 0;
  outline: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 4px;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 160px;
  min-height: 24px;
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 0 8px;
  font-size: calc(12px * var(--font-scale));
}

.tag-pill span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cover-zone {
  display: flex;
  min-width: 0;
}

.cover-drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  flex: 1;
  border: 1px dashed var(--color-border-strong);
  border-radius: 16px;
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  padding: 12px;
  text-align: center;
  cursor: pointer;
}

.cover-drop:hover,
.cover-drop.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.cover-drop span {
  max-width: 100%;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 500;
  overflow-wrap: anywhere;
}

.cover-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 12px;
}

.file-zone {
  padding: 14px 16px 0;
}

.text-zone,
.url-zone {
  padding: 14px 16px 0;
}

.text-content-field {
  display: grid;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.text-content-field textarea {
  width: 100%;
  min-height: 168px;
  border: 1px solid var(--color-border-strong);
  border-radius: 12px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 12px 14px;
  resize: vertical;
  outline: none;
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
}

.text-content-field textarea:focus {
  border-color: var(--color-primary);
}

.url-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 0 14px;
}

.url-input-wrap:focus-within {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.url-input-wrap input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.file-drop {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-height: 168px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 16px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 16px;
  cursor: pointer;
  font-size: calc(13px * var(--font-scale));
}

.file-drop:hover,
.file-drop.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.hidden-input {
  display: none;
}

.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px;
}

.source-mode-actions,
.submit-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.source-mode-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast),
    transform 160ms ease;
}

.source-mode-btn:hover,
.source-mode-btn.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.source-mode-btn:active {
  transform: translateY(1px);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
}

.icon-btn:hover {
  background: color-mix(in srgb, var(--color-text-secondary) 10%, transparent);
  color: var(--color-text);
}

.secondary-btn,
.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 0 16px;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.primary-btn {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

@media (max-width: 720px) {
  .upper-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .dialog-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .source-mode-actions,
  .submit-actions {
    justify-content: flex-end;
  }
}
</style>
