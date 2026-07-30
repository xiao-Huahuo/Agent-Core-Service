<!--
  Lazy recent-file thumbnail.

  Usage:
  Displays the material file icon by default and loads image previews only
  when the thumbnail enters the viewport.
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { buildApiUrl } from '@/api/client'
import { previewKnowledgeFile } from '@/api/knowledge'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import { useSettingsStore } from '@/stores/settings'
import type { KnowledgeFileNode } from '@/types/knowledge'
import { isImageFilePath } from '@/utils/recentFileHistory'

const props = defineProps<{
  node: KnowledgeFileNode
}>()

const settingsStore = useSettingsStore()
const root = ref<HTMLElement | null>(null)
const previewUrl = ref('')
const previewFailed = ref(false)
const materialIcon = computed(() => materialFileIconForNode(props.node))
let observer: IntersectionObserver | null = null

/** Loads an image preview after the reserved thumbnail becomes visible. */
async function loadPreview() {
  if (!isImageFilePath(props.node.path) || previewUrl.value || previewFailed.value) return
  try {
    const preview = await previewKnowledgeFile(settingsStore.profile.userId, props.node.path)
    previewUrl.value = preview.data_url || (preview.raw_url ? buildApiUrl(preview.raw_url) : '')
    previewFailed.value = !previewUrl.value
  } catch {
    previewFailed.value = true
  }
}

onMounted(() => {
  if (!isImageFilePath(props.node.path) || !root.value) return
  observer = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return
    observer?.disconnect()
    observer = null
    void loadPreview()
  }, { rootMargin: '80px' })
  observer.observe(root.value)
})

onUnmounted(() => observer?.disconnect())
</script>

<template>
  <span ref="root" class="recent-file-thumbnail" aria-hidden="true">
    <img
      v-if="previewUrl"
      class="recent-file-preview"
      :src="previewUrl"
      :alt="node.name"
      loading="lazy"
    />
    <img v-else class="recent-file-icon" :src="materialIcon.src" :alt="materialIcon.alt" />
  </span>
</template>

<style scoped>
.recent-file-thumbnail {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
}

.recent-file-icon {
  width: 26px;
  height: 26px;
}

.recent-file-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
