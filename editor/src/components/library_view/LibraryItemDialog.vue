<!--
  Library item edit dialog.

  Usage:
  Edits virtual metadata and exposes a type-aware real-content view for books.
  It never renames or moves the real source file.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import LibraryTagPicker from '@/components/library_view/LibraryTagPicker.vue'
import LibraryRealContentPanel from '@/components/library_view/LibraryRealContentPanel.vue'
import { uploadLibraryCover } from '@/api/library'
import type { LibraryItem, LibraryTag } from '@/types/knowledge'

const props = defineProps<{
  open: boolean
  userId: string
  item: LibraryItem | null
  availableTags: LibraryTag[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: {
    title: string
    description: string
    cover_mode: LibraryItem['cover_mode']
    cover_asset_id: string
    tags: string[]
    source_content?: string
  }]
  openFile: [item: LibraryItem]
  openUrl: [url: string]
}>()

const title = ref('')
const description = ref('')
const coverMode = ref<LibraryItem['cover_mode']>('icon')
const coverAssetId = ref('')
const tags = ref<string[]>([])
const uploading = ref(false)
const coverDragActive = ref(false)
const coverPreviewUrl = ref('')
const uploadInput = ref<HTMLInputElement | null>(null)
const editMode = ref<'metadata' | 'content'>('metadata')
const realContent = ref('')
const originalRealContent = ref('')
const realContentDirty = ref(false)

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
    coverDragActive.value = false
    editMode.value = 'metadata'
    realContent.value = ''
    originalRealContent.value = ''
    realContentDirty.value = false
  },
  { immediate: true },
)

function submit() {
  emit('save', {
    title: title.value.trim(),
    description: description.value.trim(),
    cover_mode: coverMode.value,
    cover_asset_id: coverAssetId.value,
    tags: tags.value,
    source_content: realContentDirty.value ? realContent.value : undefined,
  })
}

function handleRealContentLoaded(content: string) {
  realContent.value = content
  originalRealContent.value = content
  realContentDirty.value = false
}

function handleRealContentChange(content: string) {
  realContent.value = content
  realContentDirty.value = content !== originalRealContent.value
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
    <section class="dialog-panel library-form-surface" role="dialog" aria-modal="true">
        <header class="dialog-head">
          <h2>{{ isCollection ? '编辑集锦' : '编辑图书' }}</h2>
          <button class="icon-btn" type="button" title="关闭" @click="emit('close')">
            <IcIcon name="close" :size="16" />
          </button>
        </header>

        <section class="upper-grid">
          <div v-if="editMode === 'metadata'" class="metadata-zone">
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
              <LibraryTagPicker v-model="tags" :available-tags="availableTags.map((tag) => tag.name)" />
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

          <LibraryRealContentPanel
            v-if="editMode === 'content'"
            class="real-content-zone"
            :item="item"
            :user-id="userId"
            @open-file="emit('openFile', $event)"
            @open-url="emit('openUrl', $event)"
            @content-loaded="handleRealContentLoaded"
            @content-change="handleRealContentChange"
          />
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

        <footer class="dialog-actions" :class="{ 'with-mode-toggle': !isCollection }">
          <div
            v-if="!isCollection"
            class="mode-toggle"
            :class="{ 'content-active': editMode === 'content' }"
            role="group"
            aria-label="编辑内容模式"
          >
            <button
              class="mode-toggle-option"
              :class="{ active: editMode === 'metadata' }"
              type="button"
              @click="editMode = 'metadata'"
            >元信息</button>
            <button
              class="mode-toggle-option"
              :class="{ active: editMode === 'content' }"
              type="button"
              @click="editMode = 'content'"
            >元文件</button>
          </div>
          <div class="dialog-submit-actions">
            <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
            <button class="primary-btn" type="button" @click="submit">
              <IcIcon name="save" :size="14" />
              保存
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
  border-radius: 28px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 7px 16px;
}

.dialog-head h2 {
  margin: 0;
  font-size: calc(15px * var(--font-scale));
}

.upper-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 5fr);
  gap: 14px;
  padding: 16px 16px 0;
}

.metadata-zone {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
}

.field {
  display: grid;
  min-width: 0;
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
  border-radius: 28px;
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

.cover-zone {
  display: flex;
  min-width: 0;
  order: -1;
}

.real-content-zone {
  min-width: 0;
  min-height: 0;
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
  border-radius: 28px;
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
  border-radius: 28px;
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

.dialog-actions.with-mode-toggle {
  justify-content: space-between;
}

.dialog-submit-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.mode-toggle {
  position: relative;
  isolation: isolate;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.mode-toggle::before {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 3px;
  z-index: -1;
  width: calc(50% - 4px);
  border-radius: 999px;
  background: var(--color-primary-soft);
  content: '';
  transition: transform 220ms ease;
}

.mode-toggle.content-active::before {
  transform: translateX(calc(100% + 2px));
}

.mode-toggle-option {
  position: relative;
  z-index: 1;
  min-height: 28px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  padding: 0 12px;
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
  transition: color 180ms ease, transform 180ms ease;
}

.mode-toggle-option.active {
  color: var(--color-primary);
  font-weight: 700;
}

.mode-toggle-option:active {
  transform: scale(0.96);
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
