<!--
  Library create dialog.

  Usage:
  Creates a virtual library book or collection. Book creation collects virtual
  metadata, an optional cover image key, and one dragged or selected real file.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ImagePlus, Save, UploadCloud, X, XCircle } from 'lucide-vue-next'

import { uploadLibraryCover } from '@/api/library'
import type { LibraryItem } from '@/types/knowledge'

type CreateMode = 'book' | 'collection'

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
  }]
}>()

const title = ref('')
const description = ref('')
const tags = ref<string[]>([])
const tagDraft = ref('')
const coverAssetId = ref('')
const coverPreviewUrl = ref('')
const realFile = ref<File | null>(null)
const coverUploading = ref(false)
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
    dragActive.value = false
  },
)

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
  coverUploading.value = true
  try {
    const response = await uploadLibraryCover(props.userId, file)
    coverAssetId.value = response.asset?.asset_id ?? ''
    coverPreviewUrl.value = response.asset?.url ?? ''
  } finally {
    coverUploading.value = false
    input.value = ''
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
              <span>Description</span>
              <textarea v-model="description" rows="5" placeholder="用于搜索和归纳说明" />
            </label>
            <div class="field">
              <span>标签</span>
              <div class="tag-editor">
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
                <input
                  v-model="tagDraft"
                  type="text"
                  spellcheck="false"
                  placeholder="输入后回车"
                  @blur="addTag()"
                  @keydown="handleTagKeydown"
                />
              </div>
            </div>
          </div>

          <div class="cover-zone">
            <input ref="coverInput" class="hidden-input" type="file" accept="image/*" @change="uploadCover" />
            <button class="cover-drop" type="button" :disabled="coverUploading" @click="coverInput?.click()">
              <img v-if="coverPreviewUrl" class="cover-preview" :src="coverPreviewUrl" alt="" />
              <template v-else>
                <ImagePlus :size="30" />
                <span>{{ title || '标题 Key' }}</span>
              </template>
            </button>
          </div>
        </section>

        <section v-if="isBook" class="file-zone">
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

        <footer class="dialog-actions">
          <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
          <button class="primary-btn" type="button" @click="submit">
            <Save :size="14" />
            创建
          </button>
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
  font-size: 16px;
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
  font-size: 12px;
  color: var(--color-text-secondary);
}

.field input[type="text"],
.field textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 8px 10px;
  resize: vertical;
}

.tag-editor {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-canvas);
  padding: 5px;
}

.tag-editor input {
  flex: 1 1 120px;
  min-width: 90px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
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
  font-size: 12px;
}

.tag-pill span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cover-zone {
  min-width: 0;
}

.cover-drop {
  display: grid;
  place-items: center;
  gap: 10px;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border: 1px dashed var(--color-border-strong);
  border-radius: 6px;
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  padding: 12px;
  text-align: center;
}

.cover-drop:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.cover-drop span {
  max-width: 100%;
  color: var(--color-text);
  font-size: 16px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.cover-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.file-zone {
  padding: 14px 16px 0;
}

.file-drop {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-height: 112px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 6px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 16px;
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
  justify-content: flex-end;
  gap: 8px;
  padding: 16px;
}

.icon-btn,
.secondary-btn,
.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 6px 10px;
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
}
</style>
