<!--
  Library item edit dialog.

  Usage:
  Edits virtual metadata only: title, description, cover mode, tags, and cover
  image. It never renames or moves the real source file.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ImagePlus, Save, X } from 'lucide-vue-next'

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
const tagText = ref('')
const uploading = ref(false)
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
    tagText.value = item?.tags.join(', ') ?? ''
  },
  { immediate: true },
)

function submit() {
  emit('save', {
    title: title.value.trim(),
    description: description.value.trim(),
    cover_mode: coverMode.value,
    cover_asset_id: coverAssetId.value,
    tags: tagText.value.split(',').map((tag) => tag.trim()).filter(Boolean),
  })
}

async function uploadCover(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.userId) return
  uploading.value = true
  try {
    const response = await uploadLibraryCover(props.userId, file)
    coverAssetId.value = response.asset?.asset_id ?? ''
    coverMode.value = 'image'
  } finally {
    uploading.value = false
    input.value = ''
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
            <X :size="16" />
          </button>
        </header>

        <label class="field">
          <span>图书馆假名</span>
          <input v-model="title" type="text" spellcheck="false" placeholder="留空使用默认名称" />
        </label>
        <label class="field">
          <span>描述</span>
          <textarea v-model="description" rows="4" placeholder="用于封面文字、搜索和归纳说明" />
        </label>
        <label class="field">
          <span>标签</span>
          <input v-model="tagText" type="text" spellcheck="false" placeholder="用英文逗号分隔" />
        </label>
        <div class="field">
          <span>封面 Key</span>
          <div class="cover-options">
            <label><input v-model="coverMode" type="radio" value="icon" /> 文件类型图标</label>
            <label><input v-model="coverMode" type="radio" value="title" /> 标题文字</label>
            <label><input v-model="coverMode" type="radio" value="description" /> 描述文字</label>
            <label><input v-model="coverMode" type="radio" value="image" /> 上传图片</label>
            <label v-if="canUseSourceImage"><input v-model="coverMode" type="radio" value="source_image" /> 使用真实图片</label>
          </div>
          <input ref="uploadInput" class="hidden-input" type="file" accept="image/*" @change="uploadCover" />
          <button class="secondary-btn" type="button" :disabled="uploading" @click="uploadInput?.click()">
            <ImagePlus :size="14" />
            {{ uploading ? '上传中' : '上传封面' }}
          </button>
        </div>

        <footer class="dialog-actions">
          <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
          <button class="primary-btn" type="button" @click="submit">
            <Save :size="14" />
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
  width: min(520px, calc(100vw - 32px));
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.dialog-head h2 {
  margin: 0;
  font-size: 16px;
}

.dialog-head p {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.field {
  display: grid;
  gap: 8px;
  padding: 14px 16px 0;
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

.cover-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.cover-options label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text);
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
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 7px 10px;
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
</style>
