<!--
  Global image preview overlay.

  Features:
  - Floating card with frosted-glass backdrop ("液态玻璃" suspension effect)
  - Multi-image navigation (prev / next) with pagination counter at bottom
  - Mouse-wheel zoom toward cursor + drag pan when zoomed
  - Top toolbar with icon+text capsule actions
  - Show in system file explorer (Electron desktop only)
  - Download, copy URL, reset zoom
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useImagePreviewer } from '@/components/common/useImagePreviewer'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const {
  images,
  currentIndex,
  isOpen,
  currentImage,
  hasNext,
  hasPrev,
  close,
  next,
  prev,
} = useImagePreviewer()

const containerRef = ref<HTMLDivElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }
const imageLoaded = ref(false)
const naturalSize = ref({ width: 0, height: 0 })
const showCopyTip = ref(false)

/* ---------- helpers ---------- */

function resetZoom() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

/** Whether the current image is a local knowledge-base file. */
const isLocalFile = computed(() => {
  const src = currentImage.value?.src || ''
  return src.includes('/knowledge/files/raw') || src.includes('knowledge%2Ffiles%2Fraw')
})

/** Resolve a knowledge URL to an absolute local path. */
function resolveLocalPath(src: string): string {
  try {
    const url = new URL(src, window.location.origin)
    const path = url.searchParams.get('path') || ''
    if (path) {
      const knowledgeDir = settingsStore.profile.knowledgeDir.replace(/\\/g, '/')
      return `${knowledgeDir}/${path.replace(/\\/g, '/')}`
    }
  } catch { /* fall through */ }
  return src
}

/* ---------- event handlers ---------- */

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    close()
  } else if (e.key === 'ArrowRight') {
    next()
  } else if (e.key === 'ArrowLeft') {
    prev()
  }
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  const newScale = Math.max(0.2, Math.min(10, scale.value + delta))
  const rect = imageRef.value?.getBoundingClientRect()
  if (rect) {
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const ratio = newScale / scale.value
    translateX.value = mx - ratio * (mx - translateX.value)
    translateY.value = my - ratio * (my - translateY.value)
  }
  scale.value = newScale
}

function onPointerDown(e: PointerEvent) {
  isDragging.value = true
  dragStart.x = e.clientX - translateX.value
  dragStart.y = e.clientY - translateY.value
  if (imageRef.value) {
    imageRef.value.setPointerCapture(e.pointerId)
  }
}

function onPointerMove(e: PointerEvent) {
  if (!isDragging.value) return
  translateX.value = e.clientX - dragStart.x
  translateY.value = e.clientY - dragStart.y
}

function onPointerUp() {
  isDragging.value = false
}

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  naturalSize.value = { width: img.naturalWidth, height: img.naturalHeight }
  imageLoaded.value = true
}

function onImageError() {
  imageLoaded.value = false
  naturalSize.value = { width: 0, height: 0 }
}

function downloadImage() {
  const img = currentImage.value
  if (!img) return
  const a = document.createElement('a')
  a.href = img.src
  a.download = img.alt || 'image'
  a.target = '_blank'
  a.rel = 'noopener noreferrer'
  a.click()
}

function copyImageUrl() {
  const img = currentImage.value
  if (!img) return
  navigator.clipboard.writeText(img.src).then(() => {
    showCopyTip.value = true
    setTimeout(() => { showCopyTip.value = false }, 1500)
  })
}

/** Show in system file explorer or open external URL. */
async function showInFolder() {
  const src = currentImage.value?.src
  if (!src || typeof window.agentEditorDesktop === 'undefined') return
  if (isLocalFile.value) {
    const localPath = resolveLocalPath(src)
    await window.agentEditorDesktop.showItemInFolder(localPath)
  } else {
    await window.agentEditorDesktop.openExternal(src)
  }
}

/* ---------- computed display ---------- */

const filename = computed(() => {
  const src = currentImage.value?.src || ''
  const alt = currentImage.value?.alt || ''

  // knowledge-base raw-file URL: extract from path param
  if (isLocalFile.value) {
    try {
      const url = new URL(src, window.location.origin)
      const pathParam = url.searchParams.get('path') || ''
      if (pathParam) {
        const parts = pathParam.replace(/\\/g, '/').split('/').filter(Boolean)
        return decodeURIComponent(parts[parts.length - 1] || '')
      }
    } catch { /* fall through */ }
  }

  // data-uri or blob: use alt text
  if (src.startsWith('data:') || src.startsWith('blob:')) {
    return alt || 'image'
  }

  // regular URL: last path segment
  try {
    const url = new URL(src)
    const parts = url.pathname.split('/').filter(Boolean)
    if (parts.length) return decodeURIComponent(parts[parts.length - 1])
  } catch { /* fall through */ }

  // fallback
  const parts = src.split('/').filter(Boolean)
  return parts.length ? decodeURIComponent(parts[parts.length - 1]) : (alt || 'image')
})

/* ---------- watchers ---------- */

watch(currentIndex, resetZoom)
watch(isOpen, (v) => {
  if (v) {
    resetZoom()
    imageLoaded.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="preview-fade">
      <div
        v-if="isOpen"
        ref="containerRef"
        class="image-previewer"
        tabindex="0"
        @keydown="onKeydown"
      >
        <!-- frosted-glass backdrop -->
        <div class="previewer-backdrop" @click="close" />

        <!-- floating card -->
        <div class="previewer-card" @click.stop>
          <!-- ====== top toolbar ====== -->
          <div class="previewer-toolbar">
            <div class="toolbar-left">
              <span v-if="naturalSize.width" class="toolbar-meta">{{ naturalSize.width }} × {{ naturalSize.height }}</span>
              <span v-if="scale !== 1" class="toolbar-zoom">{{ Math.round(scale * 100) }}%</span>
            </div>

            <div class="toolbar-center">
              <span class="toolbar-filename" :title="filename">{{ filename }}</span>
            </div>

            <div class="toolbar-right">
              <button class="toolbar-btn capsule" title="重置缩放" @click="resetZoom">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35M8 11h6"/>
                </svg>
                <span>缩放</span>
              </button>
              <button class="toolbar-btn capsule" @click="copyImageUrl">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
                <span>{{ showCopyTip ? '已复制' : '复制链接' }}</span>
              </button>
              <button
                class="toolbar-btn capsule"
                :title="isLocalFile ? '在文件管理器中显示' : '在浏览器中打开'"
                @click="showInFolder"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
                </svg>
                <span>{{ isLocalFile ? '在文件夹中显示' : '在浏览器中打开' }}</span>
              </button>
              <button class="toolbar-btn capsule toolbar-btn-primary" @click="downloadImage">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span>下载</span>
              </button>
            </div>
          </div>

          <!-- ====== image stage ====== -->
          <div class="previewer-stage" @wheel.prevent="onWheel">
            <!-- circular prev/next on sides -->
            <button
              v-if="hasPrev"
              class="stage-nav stage-nav-prev"
              title="上一张（←）"
              @click.stop="prev"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>
            <button
              v-if="hasNext"
              class="stage-nav stage-nav-next"
              title="下一张（→）"
              @click.stop="next"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>

            <Transition name="preview-zoom" mode="out-in">
              <div
                :key="currentIndex"
                class="previewer-image-wrap"
                :class="{ dragging: isDragging, loaded: imageLoaded }"
                :style="{
                  transform: `translate(${translateX}px, ${translateY}px) scale(${scale})`,
                }"
                @pointerdown="onPointerDown"
                @pointermove="onPointerMove"
                @pointerup="onPointerUp"
                @pointercancel="onPointerUp"
              >
                <img
                  ref="imageRef"
                  :src="currentImage?.src"
                  :alt="currentImage?.alt || ''"
                  class="previewer-image"
                  @load="onImageLoad"
                  @error="onImageError"
                  draggable="false"
                />
              </div>
            </Transition>
          </div>
        </div>

        <!-- ====== close button (page-level top-right) ====== -->
        <button class="previewer-close" title="关闭（Esc）" @click="close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        <!-- ====== bottom pagination ====== -->
        <div class="previewer-pagination">
          <span class="page-indicator">{{ currentIndex + 1 }} / {{ images.length }}</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ---- backdrop (frosted glass) ---- */
.previewer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.82);
  backdrop-filter: blur(20px) saturate(0.7);
  -webkit-backdrop-filter: blur(20px) saturate(0.7);
  cursor: pointer;
}

/* ---- root ---- */
.image-previewer {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  outline: none;
  user-select: none;
}

/* ---- floating card ---- */
.previewer-card {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(94vw, 1400px);
  height: min(88vh, 900px);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.08),
    0 24px 80px rgba(0, 0, 0, 0.5),
    0 8px 24px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

/* ---- circular stage nav arrows ---- */
.stage-nav {
  position: absolute;
  top: 50%;
  z-index: 3;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.25s, background 0.2s, transform 0.2s;
}
.previewer-card:hover .stage-nav {
  opacity: 0.7;
}
.stage-nav:hover {
  opacity: 1 !important;
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-50%) scale(1.08);
}
.stage-nav-prev { left: 12px; }
.stage-nav-next { right: 12px; }

/* ======== top toolbar ======== */
.previewer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.toolbar-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: rgba(255, 255, 255, 0.7);
  font-family: var(--font-ui, system-ui, sans-serif);
  font-size: 13px;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.7);
  font-family: var(--font-ui, system-ui, sans-serif);
  font-size: 13px;
}

.toolbar-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.toolbar-filename {
  color: rgba(255, 255, 255, 0.9);
}

.toolbar-meta {
  font-variant-numeric: tabular-nums;
  opacity: 0.6;
}

.toolbar-zoom {
  color: #4fc3f7;
}

/* ---- capsule buttons ---- */
.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: 0;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  font-family: inherit;
  font-size: 12.5px;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, opacity 0.15s;
}
.toolbar-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}
.toolbar-btn:disabled {
  opacity: 0.3;
  cursor: default;
}
.toolbar-btn-primary {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}
.toolbar-btn-primary:hover {
  background: rgba(255, 255, 255, 0.22) !important;
}

/* ---- close button (page-level top-right) ---- */
.previewer-close {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 10;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.2s, background 0.2s;
}
.previewer-close:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
}

/* ======== stage ======== */
.previewer-stage {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  overflow: hidden;
}

.previewer-image-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  max-height: 100%;
  border-radius: 6px;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.06),
    0 8px 40px rgba(0, 0, 0, 0.4),
    0 2px 8px rgba(0, 0, 0, 0.25);
  cursor: grab;
  transition: box-shadow 0.3s;
}
.previewer-image-wrap.dragging {
  cursor: grabbing;
}

.previewer-image {
  display: block;
  max-width: 100%;
  max-height: 100%;
  border-radius: 6px;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.02);
  opacity: 0;
  transition: opacity 0.3s;
}
.previewer-image-wrap.loaded .previewer-image {
  opacity: 1;
}

/* ======== bottom pagination ======== */
.previewer-pagination {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  padding: 6px 16px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: rgba(255, 255, 255, 0.7);
  font-family: var(--font-ui, system-ui, sans-serif);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

/* ======== transitions ======== */
.previewer-fade-enter-active,
.previewer-fade-leave-active {
  transition: opacity 0.25s ease;
}
.previewer-fade-enter-from,
.previewer-fade-leave-to {
  opacity: 0;
}

.previewer-zoom-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.previewer-zoom-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.previewer-zoom-enter-from {
  opacity: 0;
  transform: scale(0.92);
}
.previewer-zoom-leave-to {
  opacity: 0;
  transform: scale(1.04);
}
</style>
