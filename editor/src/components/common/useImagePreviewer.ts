import { computed, ref } from 'vue'

export interface ImagePreviewItem {
  src: string
  alt?: string
  sourceUrl?: string
}

const images = ref<ImagePreviewItem[]>([])
const currentIndex = ref(0)
const isOpen = ref(false)
let resolveCallback: ((value: boolean) => void) | null = null

export function useImagePreviewer() {
  const currentImage = computed(() => images.value[currentIndex.value] ?? null)
  const hasNext = computed(() => currentIndex.value < images.value.length - 1)
  const hasPrev = computed(() => currentIndex.value > 0)

  function open(items: ImagePreviewItem[], index = 0) {
    images.value = items
    currentIndex.value = index
    isOpen.value = true
  }

  function openAsync(items: ImagePreviewItem[], index = 0): Promise<boolean> {
    open(items, index)
    return new Promise<boolean>((resolve) => {
      resolveCallback = resolve
    })
  }

  function close() {
    isOpen.value = false
    resolveCallback?.(false)
    resolveCallback = null
  }

  function next() {
    if (hasNext.value) {
      currentIndex.value++
    }
  }

  function prev() {
    if (hasPrev.value) {
      currentIndex.value--
    }
  }

  function goTo(index: number) {
    if (index >= 0 && index < images.value.length) {
      currentIndex.value = index
    }
  }

  return {
    images,
    currentIndex,
    isOpen,
    currentImage,
    hasNext,
    hasPrev,
    open,
    openAsync,
    close,
    next,
    prev,
    goTo,
  }
}
