<!--
  Markdown preview surface.

  Usage:
  Hosts a read-only Vditor instance and exposes only its preview pane. This
  keeps Preview/Split rendering on the same internal Vditor pipeline as Edit,
  including headings, code block previews, diagrams, and math blocks.
-->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue'
import Vditor from 'vditor'

import {
  decorateRenderedMarkdownImages,
  rewriteMarkdownImageUrls,
} from '@/components/editor_workspace/markdownImageUrls'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

const props = defineProps<{
  content: string
  path?: string
}>()

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

type VditorPreviewInternals = Vditor & {
  vditor?: {
    preview?: {
      element?: HTMLElement
      previewElement?: HTMLElement
    }
  }
}

const previewHost = ref<HTMLDivElement | null>(null)
let instance: Vditor | null = null
let mounted = false
let renderVersion = 0

function decodeUrlPath(path: string) {
  try {
    return decodeURIComponent(path)
  } catch {
    return path
  }
}

function getImageUrlContext() {
  const filePath = props.path || workspaceStore.selectedPath
  const userId = settingsStore.profile.userId
  return { currentFilePath: filePath, userId }
}

function getPreviewElement() {
  const internalPreview = (instance as VditorPreviewInternals | null)?.vditor?.preview?.element
  return internalPreview ?? previewHost.value?.querySelector<HTMLElement>('.vditor-preview') ?? null
}

function ensurePreviewPaneIsRenderable() {
  const previewElement = getPreviewElement()
  if (!previewElement) {
    return
  }
  // Guardrail: Vditor.preview.render() checks preview.element.style.display,
  // not computed CSS. Scoped display:block CSS is insufficient if the inline
  // value was left as "none", so this must run before every renderPreview().
  previewElement.style.display = 'block'
}

function fixImageUrls() {
  const previewEl = getPreviewElement()
  if (!previewEl) {
    return
  }
  const context = getImageUrlContext()
  if (!context.currentFilePath || !context.userId) {
    return
  }
  decorateRenderedMarkdownImages(previewEl, context)
}

function getAnchorHash(link: HTMLAnchorElement) {
  const href = link.getAttribute('href') || ''
  if (href.startsWith('#')) {
    return href
  }
  try {
    const url = new URL(href, window.location.href)
    if (!url.hash) {
      return ''
    }
    const currentWithoutHash = `${window.location.origin}${window.location.pathname}${window.location.search}`
    const targetWithoutHash = `${url.origin}${url.pathname}${url.search}`
    return targetWithoutHash === currentWithoutHash ? url.hash : ''
  } catch {
    return ''
  }
}

function findAnchorTarget(root: HTMLElement, hash: string) {
  const decoded = decodeUrlPath(hash.slice(1))
  if (!decoded) {
    return null
  }
  const escaped = CSS.escape(decoded)
  const rawEscaped = CSS.escape(hash.slice(1))
  const byIdOrName = (
    root.querySelector<HTMLElement>(`#${escaped}`)
    ?? root.querySelector<HTMLElement>(`[name="${escaped}"]`)
    ?? root.querySelector<HTMLElement>(`#${rawEscaped}`)
    ?? root.querySelector<HTMLElement>(`[name="${rawEscaped}"]`)
  )
  if (byIdOrName) {
    return byIdOrName
  }
  const normalizedTargetText = decoded.replace(/[-_\s]+/g, '').toLowerCase()
  const headings = root.querySelectorAll<HTMLElement>('h1,h2,h3,h4,h5,h6')
  return [...headings].find((heading) => {
    const headingText = (heading.textContent ?? '').trim()
    return headingText === decoded
      || headingText.replace(/[-_\s]+/g, '').toLowerCase() === normalizedTargetText
  }) ?? null
}

function getPreviewScrollContainer(target: HTMLElement) {
  const previewEl = getPreviewElement()
  if (previewEl?.contains(target)) {
    return previewEl
  }
  const resetEl = previewHost.value?.querySelector<HTMLElement>('.vditor-reset')
  if (resetEl?.contains(target)) {
    return resetEl
  }
  return null
}

function syncPreviewContent() {
  if (!instance) {
    return
  }
  try {
    const renderContent = rewriteMarkdownImageUrls(props.content, getImageUrlContext())
    if (instance.getValue() !== renderContent) {
      instance.setValue(renderContent, true)
    }
    ensurePreviewPaneIsRenderable()
    instance.renderPreview()
    fixImageUrls()
  } catch (err) {
    console.warn('[MarkdownPreview] syncPreviewContent failed:', err)
  }
}

function waitForAnimationFrame() {
  return new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

async function queuePreviewRender() {
  const version = ++renderVersion
  await nextTick()
  await waitForAnimationFrame()
  if (!mounted || version !== renderVersion) {
    return
  }
  syncPreviewContent()
}

function handleClick(event: MouseEvent) {
  const eventTarget = event.target instanceof Element ? event.target : null
  const link = eventTarget?.closest<HTMLAnchorElement>('a[href]')
  if (!link) {
    return
  }
  const hash = getAnchorHash(link)
  if (!hash || hash === '#') {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  const root = previewHost.value
  if (!root) {
    return
  }
  const target = findAnchorTarget(root, hash)
  if (!target) {
    return
  }
  const previewEl = getPreviewScrollContainer(target)
  if (previewEl) {
    const previewRect = previewEl.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const top = previewEl.scrollTop + targetRect.top - previewRect.top - 12
    previewEl.scrollTo({ top, behavior: 'smooth' })
    return
  }
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  if (!previewHost.value) {
    return
  }
  previewHost.value.addEventListener('click', handleClick, { capture: true })
  try {
    instance = new Vditor(previewHost.value, {
      value: rewriteMarkdownImageUrls(props.content, getImageUrlContext()),
      height: '100%',
      mode: 'sv',
      cache: { enable: false },
      preview: {
        delay: 0,
        mode: 'both',
        actions: [],
        markdown: {
          codeBlockPreview: true,
          mathBlockPreview: true,
        },
      },
      after() {
        mounted = true
        try { instance?.disabledCache() } catch { /* best-effort */ }
        try { instance?.clearCache() } catch { /* best-effort */ }
        void queuePreviewRender()
      },
    })
  } catch (err) {
    console.warn('[MarkdownPreview] Vditor init failed:', err)
  }
})

onUnmounted(() => {
  previewHost.value?.removeEventListener('click', handleClick, { capture: true })
})

watch(
  () => [props.content, props.path],
  () => {
    if (!mounted) {
      return
    }
    void queuePreviewRender()
  },
)

onBeforeUnmount(() => {
  mounted = false
  try {
    instance?.destroy()
  } catch (err) {
    console.warn('[MarkdownPreview] destroy failed:', err)
  }
  instance = null
})
</script>

<template>
  <article class="markdown-preview">
    <div ref="previewHost" class="markdown-preview-renderer"></div>
  </article>
</template>

<style scoped>
.markdown-preview {
  display: flex;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
}

.markdown-preview-renderer {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.markdown-preview :deep(.vditor) {
  width: 100%;
  height: 100% !important;
  border: 0 !important;
  background: transparent !important;
}

/* Keep these hides scoped to MarkdownPreview. Do not globally hide
   .vditor-preview or Split/Preview rendering will regress. */
.markdown-preview :deep(.vditor-toolbar),
.markdown-preview :deep(.vditor-sv),
.markdown-preview :deep(.vditor-ir),
.markdown-preview :deep(.vditor-wysiwyg) {
  display: none !important;
}

.markdown-preview :deep(.vditor-content) {
  display: block !important;
  width: 100% !important;
  height: 100% !important;
}

.markdown-preview :deep(.vditor-preview) {
  display: block !important;
  width: 100% !important;
  height: 100% !important;
  overflow: auto;
  background: transparent !important;
}

.markdown-preview :deep(.vditor-preview > .vditor-reset) {
  max-width: none !important;
  min-height: 100%;
  margin: 0 !important;
  padding: var(--space-20) !important;
  color: var(--color-text-secondary) !important;
  font-family: var(--font-text) !important;
}

.markdown-preview :deep(.vditor-reset li)::marker {
  color: var(--color-primary);
}

.markdown-preview :deep(h1) { color: var(--color-primary) !important; font-size: calc(2rem * var(--font-scale)) !important; }
.markdown-preview :deep(h2) { color: color-mix(in srgb, var(--color-primary) 86.7%, white) !important; font-size: calc(1.35rem * var(--font-scale)) !important; }
.markdown-preview :deep(h3) { color: color-mix(in srgb, var(--color-primary) 73.3%, white) !important; font-size: calc(1.05rem * var(--font-scale)) !important; }
.markdown-preview :deep(h4) { color: color-mix(in srgb, var(--color-primary) 60%, white) !important; font-size: calc(0.9rem * var(--font-scale)) !important; }
.markdown-preview :deep(h5) { color: color-mix(in srgb, var(--color-primary) 46.7%, white) !important; font-size: calc(0.825rem * var(--font-scale)) !important; }
.markdown-preview :deep(h6) { color: color-mix(in srgb, var(--color-primary) 33.3%, white) !important; font-size: calc(0.75rem * var(--font-scale)) !important; }

.markdown-preview :deep(pre),
.markdown-preview :deep(code) {
  font-family: var(--font-code) !important;
}

.markdown-preview :deep(a) {
  color: var(--color-primary) !important;
}

.markdown-preview :deep(img.markdown-image) {
  max-width: 100%;
  height: auto;
  vertical-align: middle;
}

.markdown-preview :deep(p.markdown-image-block) {
  display: flex;
  justify-content: center;
  margin: var(--space-16) 0;
}

.markdown-preview :deep(p.markdown-image-block > img.markdown-image) {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: min(72vh, 960px);
  object-fit: contain;
}

.markdown-preview :deep(blockquote) {
  border-left-color: var(--color-primary) !important;
  color: var(--color-text-muted) !important;
}
</style>
