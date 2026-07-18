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

import { buildApiUrl } from '@/api/client'
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

function splitUrlReference(src: string) {
  const normalizedSrc = src.trim().replace(/^<|>$/g, '')
  const hashIndex = normalizedSrc.indexOf('#')
  const queryIndex = normalizedSrc.indexOf('?')
  const indexes = [hashIndex, queryIndex].filter((index) => index >= 0)
  const splitAt = indexes.length > 0 ? Math.min(...indexes) : -1
  return splitAt >= 0 ? normalizedSrc.slice(0, splitAt) : normalizedSrc
}

function decodeUrlPath(path: string) {
  try {
    return decodeURIComponent(path)
  } catch {
    return path
  }
}

function normalizeKnowledgePath(path: string) {
  const parts: string[] = []
  for (const part of path.replace(/\\/g, '/').split('/')) {
    if (!part || part === '.') {
      continue
    }
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/')
}

function resolveMarkdownAssetPath(currentFilePath: string, rawSrc: string) {
  const srcPath = decodeUrlPath(splitUrlReference(rawSrc)).replace(/\\/g, '/')
  if (!srcPath) {
    return ''
  }
  if (srcPath.startsWith('/')) {
    return normalizeKnowledgePath(srcPath)
  }
  const normalizedFilePath = currentFilePath.replace(/\\/g, '/')
  const parentDir = normalizedFilePath.includes('/')
    ? normalizedFilePath.substring(0, normalizedFilePath.lastIndexOf('/') + 1)
    : ''
  return normalizeKnowledgePath(parentDir + srcPath)
}

function isBrowserHandledAssetUrl(src: string) {
  return /^(https?:|data:|blob:|file:|about:|\/\/|#)/i.test(src)
}

function isRootRelativeAssetUrl(src: string) {
  return src.startsWith('/') && !src.startsWith('//')
}

function isKnowledgeRawUrl(src: string) {
  return src.includes('/knowledge/files/raw')
}

function buildRawFileUrl(rawSrc: string) {
  const filePath = props.path || workspaceStore.selectedPath
  const userId = settingsStore.profile.userId
  if (!filePath || !userId || isKnowledgeRawUrl(rawSrc)) {
    return rawSrc
  }
  if (isBrowserHandledAssetUrl(rawSrc) && !isRootRelativeAssetUrl(rawSrc)) {
    return rawSrc
  }
  const rawPath = resolveMarkdownAssetPath(filePath, rawSrc)
  if (!rawPath) {
    return rawSrc
  }
  return buildApiUrl('/knowledge/files/raw', {
    user_id: userId,
    path: rawPath,
  })
}

function rewriteMarkdownImageUrls(content: string) {
  let nextContent = content.replace(
    /(!\[[^\]]*]\(\s*)(<[^>]+>|[^)\n]+?)(\s+(?:"[^"]*"|'[^']*'))?\s*\)/g,
    (_match, prefix: string, rawSrc: string, suffix: string) => {
      return `${prefix}${buildRawFileUrl(rawSrc)}${suffix ?? ''})`
    },
  )
  nextContent = nextContent.replace(
    /(<img\b[^>]*\bsrc=["'])([^"']+)(["'][^>]*>)/gi,
    (_match, prefix: string, rawSrc: string, suffix: string) => {
      return `${prefix}${buildRawFileUrl(rawSrc)}${suffix}`
    },
  )
  return nextContent
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
  const filePath = props.path || workspaceStore.selectedPath
  const userId = settingsStore.profile.userId
  if (!filePath || !userId) {
    return
  }
  const imgs = previewEl.querySelectorAll<HTMLImageElement>('img[src]')
  for (const img of imgs) {
    const src = img.getAttribute('src') || ''
    if ((isBrowserHandledAssetUrl(src) && !isRootRelativeAssetUrl(src)) || isKnowledgeRawUrl(src)) {
      continue
    }
    img.src = buildRawFileUrl(src)
  }
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
    const renderContent = rewriteMarkdownImageUrls(props.content)
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
      value: rewriteMarkdownImageUrls(props.content),
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

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3),
.markdown-preview :deep(h4),
.markdown-preview :deep(h5),
.markdown-preview :deep(h6) {
  color: var(--color-text) !important;
  font-weight: 650;
}

.markdown-preview :deep(pre),
.markdown-preview :deep(code) {
  font-family: var(--font-code) !important;
}

.markdown-preview :deep(a) {
  color: var(--color-primary) !important;
}

.markdown-preview :deep(blockquote) {
  border-left-color: var(--color-primary) !important;
  color: var(--color-text-muted) !important;
}
</style>
