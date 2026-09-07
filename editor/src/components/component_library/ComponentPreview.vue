<!--
  Sandboxed component preview.

  Usage:
  Compiles Vue SFC or HTML source into iframe srcdoc. The iframe deliberately
  omits allow-same-origin so uploaded scripts cannot access the editor page.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  buildComponentPreviewDocument,
  canBuildComponentPreview,
  COMPONENT_PREVIEW_SIZE_MESSAGE,
} from '@/components/component_library/componentPreview'
import type { ComponentSourceFormat } from '@/types/componentLibrary'

defineOptions({ name: 'ComponentPreview' })

const props = defineProps<{
  source: string
  sourceFormat: ComponentSourceFormat
  label: string
}>()

const emit = defineEmits<{
  resize: [size: { width: number; height: number }]
}>()

/** Sandboxed frame used to authenticate postMessage measurements by window identity. */
const previewFrame = ref<HTMLIFrameElement | null>(null)

/** Compile source and retain a readable error instead of breaking the parent page. */
const preview = computed(() => {
  if (!canBuildComponentPreview(props.source)) {
    return {
      document: '',
      error: '源码超过 100 万字符，已关闭实时预览以保持界面流畅。',
      failed: false,
    }
  }
  try {
    return {
      document: buildComponentPreviewDocument(props.source, props.sourceFormat),
      error: '',
      failed: false,
    }
  } catch (error) {
    return {
      document: '',
      error: error instanceof Error ? error.message : '组件编译失败',
      failed: true,
    }
  }
})

/** Forward finite intrinsic dimensions only from this preview's own sandbox. */
function handlePreviewMessage(event: MessageEvent): void {
  if (event.source !== previewFrame.value?.contentWindow) return
  const data = event.data as { type?: unknown; width?: unknown; height?: unknown } | null
  const width = Number(data?.width)
  const height = Number(data?.height)
  if (data?.type !== COMPONENT_PREVIEW_SIZE_MESSAGE || !Number.isFinite(width) || !Number.isFinite(height)) return
  if (width <= 0 || height <= 0) return
  // A 100%-height absolute decoration reports the iframe viewport itself.
  // Feeding that value back into the card would add padding forever.
  const viewportHeight = previewFrame.value?.clientHeight ?? 0
  if (viewportHeight > 0 && Math.abs(height - viewportHeight) <= 1) return
  emit('resize', { width: Math.ceil(width), height: Math.ceil(height) })
}

onMounted(() => window.addEventListener('message', handlePreviewMessage))
onBeforeUnmount(() => window.removeEventListener('message', handlePreviewMessage))
</script>

<template>
  <div class="component-preview">
    <iframe
      v-if="preview.document"
      ref="previewFrame"
      :title="`${label} 实时预览`"
      :srcdoc="preview.document"
      sandbox="allow-scripts"
      scrolling="no"
      referrerpolicy="no-referrer"
    ></iframe>
    <div v-else class="preview-error" :class="{ 'preview-skipped': !preview.failed }" role="status">
      <span>{{ preview.failed ? '编译失败' : '预览已关闭' }}</span>
      <small>{{ preview.error }}</small>
    </div>
  </div>
</template>

<style scoped>
.component-preview,
.component-preview iframe {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.component-preview iframe {
  display: block;
  border: 0;
  background: transparent;
  overflow: hidden;
}

.preview-error {
  display: grid;
  place-content: center;
  gap: var(--space-6);
  height: 100%;
  padding: var(--space-16);
  color: var(--color-danger);
  text-align: center;
}

.preview-error small {
  max-width: 360px;
  color: var(--color-text-muted);
  overflow-wrap: anywhere;
}

.preview-error.preview-skipped {
  color: var(--color-text-muted);
}
</style>
