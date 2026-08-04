<!--
  Library item edit dialog.

  Usage:
  Edits virtual metadata only: title, description, cover mode, tags, and cover
  image. It never renames or moves the real source file.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { uploadLibraryCover } from '@/api/library'
import type { LibraryItem } from '@/types/knowledge'

const props = defineProps<{
  open: boolean
  userId: string
  item: LibraryItem | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { title: string; description: string; cover_mode: LibraryItem['cover_mode']; cover_asset_id: string; tags: string[] }]
}>()

const title = ref('')
const description = ref('')
const coverMode = ref<LibraryItem['cover_mode']>('icon')
const coverAssetId = ref('')
const tags = ref<string[]>([])
const tagDraft = ref('')
const uploading = ref(false)
const coverDragActive = ref(false)
const coverPreviewUrl = ref('')
const uploadInput = ref<HTMLInputElement | null>(null)

const isCollection = computed(() => props.item?.item_type === 'collection')
const canUseSourceImage = computed(() => {
  const mime = props.item?.source_mime ?? ''
  return mime.startsWith('image/')
})

watch(
  () => props.item,
  (item) => {
    title.value = item?.title ?? ''
    description.value = item?.description ?? ''
    coverMode.value = item?.cover_mode ?? 'icon'
    coverAssetId.value = item?.cover_asset_id ?? ''
    coverPreviewUrl.value = item?.cover_asset?.url ?? ''
    tags.value = item?.tags ?? []
    tagDraft.value = ''
    coverDragActive.value = false
  },
  { immediate: true },
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

function submit() {
  addTag()
  emit('save', {
    title: title.value.trim(),
    description: description.value.trim(),
    cover_mode: coverMode.value,
    cover_asset_id: coverAssetId.value,
    tags: tags.value,
  })
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
  uploading.value = true
  try {
    const response = await uploadLibraryCover(props.userId, file)
    coverAssetId.value = response.asset?.asset_id ?? ''
    coverPreviewUrl.value = response.asset?.url ?? ''
    coverMode.value = 'image'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open && item" class="dialog-backdrop" @click.self="emit('close')">
      <section class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-head">
          <div>
            <h2>{{ isCollection ? '编辑集锦' : '编辑图书' }}</h2>
            <p>{{ isCollection ? '只修改虚拟集锦信息' : item.source_name || item.source_url }}</p>
          </div>
          <button class="icon-btn" type="button" title="关闭" @click="emit('close')">
            <IcIcon name="close" :size="16" />
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
              <textarea v-model="description" rows="5" placeholder="用于封面文字、搜索和归纳说明" />
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
                  <IcIcon name="cancel" :size="13" />
                </button>
              </div>
            </div>
          </div>

          <div class="cover-zone">
            <input ref="uploadInput" class="hidden-input" type="file" accept="image/*" @change="uploadCover" />
            <button
              class="cover-drop"
              :class="{ active: coverDragActive }"
              type="button"
              :disabled="uploading"
              @click="uploadInput?.click()"
              @dragenter.prevent="coverDragActive = true"
              @dragover.prevent="coverDragActive = true"
              @dragleave.prevent="coverDragActive = false"
              @drop.prevent="dropCover"
            >
              <img v-if="coverPreviewUrl" class="cover-preview" :src="coverPreviewUrl" alt="" />
              <template v-else>
                <IcIcon name="add-photo" :size="30" />
                <span>{{ uploading ? '上传中' : '点击或拖拽上传封面' }}</span>
              </template>
            </button>
          </div>
        </section>

        <div class="field" style="padding: 10px 16px 0;">
          <span>封面模式</span>
          <div class="cover-options">
            <label><input v-model="coverMode" type="radio" value="icon" /> 文件类型图标</label>
            <label><input v-model="coverMode" type="radio" value="title" /> 标题文字</label>
            <label><input v-model="coverMode" type="radio" value="description" /> 描述文字</label>
            <label><input v-model="coverMode" type="radio" value="image" /> 上传图片</label>
            <label v-if="canUseSourceImage"><input v-model="coverMode" type="radio" value="source_image" /> 使用真实图片</label>
          </div>
        </div>

        <footer class="dialog-actions">
          <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
          <button class="primary-btn" type="button" @click="submit">
            <IcIcon name="save" :size="14" />
            保存
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

.dialog-head p {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
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

.cover-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.cover-options label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
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
  padding: 0 14px;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.primary-btn {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.secondary-btn:hover,
.icon-btn:hover {
  border-color: var(--color-border-strong);
}

@media (max-width: 720px) {
  .upper-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
