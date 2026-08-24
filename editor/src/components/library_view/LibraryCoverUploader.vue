<!--
  Shared library cover image uploader.

  Usage:
  Reuse this component wherever a persistent library asset image is needed.
  It owns click/drop selection and the existing /library/assets/cover request,
  then emits the saved asset to the parent domain form.
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { uploadLibraryCover } from '@/api/library'
import type { LibraryAsset } from '@/types/knowledge'

const props = withDefaults(defineProps<{
  userId: string
  previewUrl?: string
  emptyLabel?: string
}>(), {
  previewUrl: '',
  emptyLabel: '点击或拖拽上传封面',
})

const emit = defineEmits<{
  uploaded: [asset: LibraryAsset]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const dragActive = ref(false)
const errorMessage = ref('')

/** Upload one selected image through the persistent library asset endpoint. */
async function uploadFile(file: File) {
  if (!props.userId || !file.type.startsWith('image/')) {
    errorMessage.value = '请选择图片文件'
    return
  }
  uploading.value = true
  errorMessage.value = ''
  try {
    const response = await uploadLibraryCover(props.userId, file)
    if (response.asset) emit('uploaded', response.asset)
  } catch {
    errorMessage.value = '图片上传失败'
  } finally {
    uploading.value = false
  }
}

/** Read a file-input selection and allow choosing the same file again later. */
async function handleChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await uploadFile(file)
  input.value = ''
}

/** Accept one dropped image using the same upload path as the file input. */
async function handleDrop(event: DragEvent) {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) await uploadFile(file)
}
</script>

<template>
  <div class="library-cover-uploader">
    <input ref="inputRef" class="cover-input" type="file" accept="image/*" @change="handleChange" />
    <button
      class="cover-drop"
      :class="{ active: dragActive }"
      type="button"
      :disabled="uploading"
      :aria-label="emptyLabel"
      @click="inputRef?.click()"
      @dragenter.prevent="dragActive = true"
      @dragover.prevent="dragActive = true"
      @dragleave.prevent="dragActive = false"
      @drop.prevent="handleDrop"
    >
      <img v-if="previewUrl" class="cover-preview" :src="previewUrl" alt="" />
      <template v-else>
        <IcIcon name="add-photo" :size="30" />
        <span>{{ uploading ? '上传中' : emptyLabel }}</span>
      </template>
    </button>
    <span v-if="errorMessage" class="cover-error" role="alert">{{ errorMessage }}</span>
  </div>
</template>

<style scoped>
.library-cover-uploader {
  position: relative;
  display: flex;
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 168px;
}

.cover-input {
  display: none;
}

.cover-drop {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 12px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 28px;
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
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
  overflow-wrap: anywhere;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 500;
}

.cover-preview {
  width: 100%;
  height: 100%;
  min-height: 0;
  border-radius: 28px;
  object-fit: cover;
}

.cover-error {
  position: absolute;
  right: 12px;
  bottom: 8px;
  color: var(--color-danger);
  font-size: calc(11px * var(--font-scale));
}
</style>
