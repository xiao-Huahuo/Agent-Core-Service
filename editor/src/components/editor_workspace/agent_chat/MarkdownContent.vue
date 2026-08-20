<!--
  Markdown content renderer for editor Agent chat.

  Usage:
  Parses assistant Markdown responses with marked, sanitizes with DOMPurify,
  and highlights code blocks after Vue patches the DOM.
  Supports [N] citation anchors that navigate to knowledge source files.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { hljs, isHighlightableLanguage } from '../codeHighlight'
import { renderMathInHtml } from '../mathRender'

import { useWorkspaceStore } from '@/stores/workspace'
import type { SourceItem } from '@/stores/chat'

import { useImagePreviewer } from '@/components/common/useImagePreviewer'
import type { ImagePreviewItem } from '@/components/common/useImagePreviewer'

marked.setOptions({
  gfm: true,
  breaks: true,
})

// Register marked extension for citation anchors [N] and [K1]
const citationExtension = {
  name: 'citation',
  level: 'inline' as const,
  start(src: string) { return src.indexOf('[') },
  tokenizer(src: string) {
    const match = src.match(/^\[([A-Z]?\d+)\]/)
    if (match) {
      return {
        type: 'citation',
        raw: match[0],
        tokens: [],
        idx: match[1],
      }
    }
    return undefined
  },
  renderer(token: { idx: string }) {
    return `<sup class="citation-anchor" data-citation-idx="${token.idx}">[${token.idx}]</sup>`
  },
}
marked.use({ extensions: [citationExtension] })

const props = defineProps<{
  content: string
  isStreaming?: boolean
  citationMap?: Record<string, SourceItem>
  onNavigateSource?: (uri: string) => void
}>()

const imagePreviewer = useImagePreviewer()
const contentRef = ref<HTMLDivElement | null>(null)
const workspaceStore = useWorkspaceStore()

// 字符串级代码高亮缓存:key 为 `${lang}\0${code}`,value 为已转义的 hljs 高亮 HTML。
// 流式刷新时已完成代码块直接命中缓存,只对正在输出的最后一个代码块做真正的高亮,
// 实现"边输出边高亮"而不必等 agent 终止,同时避免整段重复词法分析拖慢渲染。
const MAX_HIGHLIGHT_CHARS = 20000
const MAX_CACHE_ENTRIES = 200
const highlightCache = new Map<string, string>()

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 覆盖 marked 的代码块渲染:在字符串层面完成高亮,输出直接进入 v-html,
// 不依赖流式结束后对 DOM 的二次遍历,因此每次刷新都带高亮。
const codeRenderer = new marked.Renderer()
codeRenderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = ((lang ?? '').split(/\s+/)[0] ?? '').trim().toLowerCase()
  const key = `${language}\u0000${text}`
  let highlighted = highlightCache.get(key)
  if (highlighted === undefined) {
    if (language && isHighlightableLanguage(language) && text.length <= MAX_HIGHLIGHT_CHARS) {
      try {
        highlighted = hljs.highlight(text, { language }).value
      } catch {
        highlighted = escapeHtml(text)
      }
    } else {
      // 未知语言或不完整超长代码:保持原样纯文本,不做可能抛错/拖慢的高亮。
      highlighted = escapeHtml(text)
    }
    if (highlightCache.size >= MAX_CACHE_ENTRIES) {
      highlightCache.clear()
    }
    highlightCache.set(key, highlighted)
  }
  const langAttr = language
    ? ` class="language-${escapeHtml(language)} hljs"`
    : ' class="hljs"'
  return `<pre><code${langAttr}>${highlighted}</code></pre>\n`
}

const sanitizedHtml = computed(() => {
  // Allow citation-anchor class, data-citation-idx attribute, img tags, and
  // KaTeX style (katex 用 style 定位上下标/strut,DOMPurify 会清洗危险 CSS)。
  const purifyConfig = {
    ALLOWED_ATTR: ['data-citation-idx', 'class', 'src', 'alt', 'referrerpolicy', 'style'],
    ADD_TAGS: ['sup', 'img'],
  }
  // 代码高亮在 renderer 内完成:代码 fence 内的 HTML 由 hljs 转义保留(不再被剥离),
  // 裸 HTML 由 DOMPurify 统一净化防 XSS。
  // 数学渲染在 marked 之后、净化之前:把 $...$ / $$...$$ 转成 KaTeX span。
  const parsed = marked.parse(props.content, { async: false, renderer: codeRenderer }) as string
  return DOMPurify.sanitize(renderMathInHtml(parsed), purifyConfig)
})

const sourceLinkSignature = computed(() => {
  const citationSources = Object.entries(props.citationMap ?? {})
    .map(([id, source]) => `${id}:${source.source_uri}`)
    .join('|')
  const workspaceSources = (workspaceStore.flatNodes ?? [])
    .filter((node) => !node.isDir && node.path)
    .map((node) => node.path)
    .join('|')
  return `${citationSources}::${workspaceSources}`
})

function handleClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  // image preview
  if (target.tagName === 'IMG' && target instanceof HTMLImageElement && target.src) {
    const root = contentRef.value
    if (root) {
      const allImgs = root.querySelectorAll<HTMLImageElement>('img[src]')
      const items: ImagePreviewItem[] = []
      let clickIndex = -1
      allImgs.forEach((img, i) => {
        if (img === target) clickIndex = i
        items.push({ src: img.src, alt: img.alt || undefined })
      })
      if (clickIndex >= 0) {
        imagePreviewer.open(items, clickIndex)
      }
    }
    return
  }
  const sourceLink = target.closest('.source-file-link') as HTMLElement | null
  if (sourceLink && props.onNavigateSource) {
    const uri = sourceLink.getAttribute('data-source-uri')
    if (uri) {
      props.onNavigateSource(uri)
    }
    return
  }
  const citation = target.closest('.citation-anchor') as HTMLElement | null
  if (!citation || !props.onNavigateSource) return
  const idx = citation.getAttribute('data-citation-idx')
  if (!idx) return
  const map = props.citationMap
  if (!map || !map[idx]) return
  props.onNavigateSource(map[idx].source_uri)
}

function sourceBaseName(uri: string): string {
  const parts = uri.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? uri
}

function sourcePath(uri: string): string {
  return uri.replace(/\\/g, '/')
}

function buildSourceLinkCandidates() {
  const map = props.citationMap ?? {}
  const basenameCounts = new Map<string, number>()
  for (const source of Object.values(map)) {
    if (!source.source_uri || /^https?:\/\//i.test(source.source_uri)) {
      continue
    }
    const name = sourceBaseName(source.source_uri)
    basenameCounts.set(name, (basenameCounts.get(name) ?? 0) + 1)
  }
  for (const node of workspaceStore.flatNodes ?? []) {
    if (node.isDir || !node.path) {
      continue
    }
    const name = sourceBaseName(node.path)
    basenameCounts.set(name, (basenameCounts.get(name) ?? 0) + 1)
  }

  const candidates: Array<{ text: string; uri: string }> = []
  const seen = new Set<string>()
  function addCandidate(text: string, uri: string) {
    if (text.length < 3) {
      return
    }
    const key = `${text}\u0000${uri}`
    if (!seen.has(key)) {
      candidates.push({ text, uri })
      seen.add(key)
    }
  }

  for (const source of Object.values(map)) {
    const uri = source.source_uri
    if (!uri || /^https?:\/\//i.test(uri)) {
      continue
    }
    const path = sourcePath(uri)
    const name = sourceBaseName(uri)
    for (const text of [path, basenameCounts.get(name) === 1 ? name : '']) {
      addCandidate(text, uri)
    }
  }
  for (const node of workspaceStore.flatNodes ?? []) {
    if (node.isDir || !node.path) {
      continue
    }
    const path = sourcePath(node.path)
    const name = sourceBaseName(node.path)
    for (const text of [path, basenameCounts.get(name) === 1 ? name : '']) {
      addCandidate(text, node.path)
    }
  }
  return candidates.sort((a, b) => b.text.length - a.text.length)
}

function shouldSkipSourceLinkNode(node: Node) {
  const parent = node.parentElement
  return !parent || Boolean(parent.closest('a, code, pre, button, .citation-anchor, .source-file-link'))
}

function findNextSourceMatch(text: string, candidates: Array<{ text: string; uri: string }>) {
  let best: { index: number; candidate: { text: string; uri: string } } | null = null
  for (const candidate of candidates) {
    const index = text.indexOf(candidate.text)
    if (index < 0) {
      continue
    }
    if (!best || index < best.index || (index === best.index && candidate.text.length > best.candidate.text.length)) {
      best = { index, candidate }
    }
  }
  return best
}

function linkSourceNames() {
  const root = contentRef.value
  if (!root) {
    return
  }
  const candidates = buildSourceLinkCandidates()
  if (candidates.length === 0) {
    return
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  let node = walker.nextNode()
  while (node) {
    if (!shouldSkipSourceLinkNode(node)) {
      textNodes.push(node as Text)
    }
    node = walker.nextNode()
  }

  for (const textNode of textNodes) {
    const original = textNode.nodeValue ?? ''
    let remaining = original
    const fragment = document.createDocumentFragment()
    let changed = false
    while (remaining) {
      const match = findNextSourceMatch(remaining, candidates)
      if (!match) {
        fragment.append(document.createTextNode(remaining))
        break
      }
      if (match.index > 0) {
        fragment.append(document.createTextNode(remaining.slice(0, match.index)))
      }
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'source-file-link'
      button.dataset.sourceUri = match.candidate.uri
      button.textContent = match.candidate.text
      fragment.append(button)
      remaining = remaining.slice(match.index + match.candidate.text.length)
      changed = true
    }
    if (changed) {
      textNode.replaceWith(fragment)
    }
  }
}

async function highlightCodeBlocks() {
  await nextTick()
  linkSourceNames()
  const root = contentRef.value
  if (!root) return
  // 代码高亮已在 sanitizedHtml(renderer)中随内容增量完成,此处只做 DOM 增强:
  // 文件名链接化与复制按钮挂接(流式结束后 v-html 不再更新,不会被冲掉)。
  // Add copy buttons to pre blocks
  root.querySelectorAll('pre').forEach((pre) => {
    if (pre.querySelector('.code-copy-btn')) return
    const btn = document.createElement('button')
    btn.className = 'code-copy-btn'
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
    btn.title = '复制代码'
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code')
      const text = code?.textContent ?? ''
      navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
        setTimeout(() => { btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' }, 1500)
      })
    })
    pre.style.position = 'relative'
    pre.appendChild(btn)
  })
}

onMounted(() => {
  contentRef.value?.addEventListener('click', handleClick)
})

onUnmounted(() => {
  contentRef.value?.removeEventListener('click', handleClick)
  highlightCache.clear()
})

watch([sanitizedHtml, sourceLinkSignature], () => {
  if (props.isStreaming) return
  void highlightCodeBlocks()
}, { immediate: true })

watch(() => props.isStreaming, (streaming, wasStreaming) => {
  if (wasStreaming && !streaming) {
    void highlightCodeBlocks()
  }
})
</script>

<template>
  <div ref="contentRef" class="markdown-body" v-html="sanitizedHtml"></div>
</template>

<style scoped>
.markdown-body {
  color: var(--color-text-primary);
  font-family: var(--font-chat);
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 var(--space-8);
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: var(--space-16) 0 var(--space-8);
  font-family: var(--font-chat);
  font-weight: 650;
  line-height: var(--line-height-tight);
}

.markdown-body :deep(h1) { color: var(--color-primary); font-size: calc(2rem * var(--font-scale)); }
.markdown-body :deep(h2) { color: color-mix(in srgb, var(--color-primary) 86.7%, white); font-size: calc(1.35rem * var(--font-scale)); }
.markdown-body :deep(h3) { color: color-mix(in srgb, var(--color-primary) 73.3%, white); font-size: calc(1.05rem * var(--font-scale)); }
.markdown-body :deep(h4) { color: color-mix(in srgb, var(--color-primary) 60%, white); font-size: calc(0.9rem * var(--font-scale)); }
.markdown-body :deep(h5) { color: color-mix(in srgb, var(--color-primary) 46.7%, white); font-size: calc(0.825rem * var(--font-scale)); }
.markdown-body :deep(h6) { color: color-mix(in srgb, var(--color-primary) 33.3%, white); font-size: calc(0.75rem * var(--font-scale)); }

.markdown-body :deep(code) {
  padding: 1px 8px;
  border: 0;
  border-radius: 999px;
  background: var(--color-code-bg);
  color: var(--color-text-primary);
  font-family: var(--font-text);
  font-size: 0.85em;
}

.markdown-body :deep(pre) {
  margin: var(--space-8) 0;
  padding: var(--space-12);
  overflow-x: auto;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-code-bg);
  line-height: 1.3;
}

.markdown-body :deep(pre code) {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-family: var(--font-text);
  font-size: var(--font-size-base);
  line-height: 1.3;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-8) 0;
  padding-left: var(--space-24);
}

.markdown-body :deep(li)::marker {
  color: var(--color-primary);
}

.markdown-body :deep(blockquote) {
  margin: var(--space-8) 0;
  padding: var(--space-8) var(--space-12);
  border-left: 2px solid var(--color-accent);
  color: var(--color-text-secondary);
}

.markdown-body :deep(a) {
  color: var(--color-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: var(--space-8) 0;
  border-collapse: collapse;
  border: 1px solid var(--color-border);
  font-size: var(--font-size-xs);
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: var(--space-6) var(--space-10);
  border: 1px solid var(--color-border-light);
  text-align: left;
}

/* Citation anchor styling */
.markdown-body :deep(.citation-anchor) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  height: auto;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: calc(9px * var(--font-scale));
  font-weight: 650;
  cursor: pointer;
  vertical-align: super;
  line-height: 1;
  transition:
    color var(--transition-fast),
    opacity var(--transition-fast);
}

.markdown-body :deep(.citation-anchor:hover) {
  background: transparent;
  color: var(--color-primary-hover);
  opacity: 1;
}

.markdown-body :deep(.source-file-link) {
  display: inline;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font: inherit;
  text-align: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(.source-file-link:hover) {
  color: var(--color-accent);
}

.markdown-body :deep(img) {
  max-width: 100%;
  max-height: min(72vh, 960px);
  height: auto;
  object-fit: contain;
  border-radius: 6px;
}

/* Copy button on code blocks */
.markdown-body :deep(.code-copy-btn) {
  position: absolute;
  top: var(--space-6);
  right: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition: opacity 160ms ease, color 160ms ease, border-color 160ms ease;
  z-index: 2;
}

.markdown-body :deep(pre:hover .code-copy-btn) {
  opacity: 1;
}

.markdown-body :deep(.code-copy-btn:hover) {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
}

</style>

<!--
  highlight.js light / dark theme.
  Switches with [data-theme] on <html> — no JS needed.
-->
<style>
/* ── base ── */
.hljs {
  color: var(--hljs-fg, #e6e6e6);
  background: transparent;
}

/* ── keywords / operators / tags ── */
.hljs-keyword,
.hljs-selector-tag,
.hljs-literal,
.hljs-section,
.hljs-link {
  color: var(--hljs-keyword, #ff79c6);
}

/* ── strings / template ── */
.hljs-string,
.hljs-addition,
.hljs-attribute,
.hljs-template-variable,
.hljs-selector-id {
  color: var(--hljs-string, #50fa7b);
}

/* ── numbers / built-in / types ── */
.hljs-number,
.hljs-built_in,
.hljs-type,
.hljs-params {
  color: var(--hljs-type, #8be9fd);
}

/* ── function names / titles ── */
.hljs-title,
.hljs-title.function_ {
  color: var(--hljs-function, #50fa7b);
}

/* ── class names ── */
.hljs-title.class_,
.hljs-title.class_.inherited__ {
  color: var(--hljs-class, #f1fa8c);
}

/* ── comments / quotes ── */
.hljs-comment,
.hljs-quote {
  color: var(--hljs-comment, #6272a4);
  font-style: italic;
}

/* ── constants / meta ── */
.hljs-literal,
.hljs-selector-attr,
.hljs-selector-pseudo,
.hljs-meta,
.hljs-meta .hljs-keyword,
.hljs-meta .hljs-string {
  color: var(--hljs-constant, #bd93f9);
}

/* ── variables / attributes ── */
.hljs-variable,
.hljs-variable.language_,
.hljs-variable.constant_ {
  color: var(--hljs-variable, #f8f8f2);
}

/* ── deletion / diff ── */
.hljs-deletion {
  color: var(--hljs-deletion, #f55);
}

/* ── attr / property / regexp ── */
.hljs-attr,
.hljs-property,
.hljs-regexp {
  color: var(--hljs-attr, #f1fa8c);
}

/* ── punctuation / operators ── */
.hljs-punctuation,
.hljs-operator {
  color: var(--hljs-operator, #ff79c6);
}

/* ── code tag / subst ── */
.hljs-subst {
  color: var(--hljs-fg, #e6e6e6);
}

/* ── doxy tags ── */
.hljs-doctag,
.hljs-doctag .hljs-keyword {
  color: var(--hljs-comment, #6272a4);
}

/* ── light theme ── */
[data-theme="light"] .hljs {
  --hljs-fg: #24292e;
  --hljs-keyword: #d73a49;
  --hljs-string: #032f62;
  --hljs-type: #6f42c1;
  --hljs-function: #6f42c1;
  --hljs-class: #e36209;
  --hljs-comment: #6a737d;
  --hljs-constant: #005cc5;
  --hljs-variable: #24292e;
  --hljs-deletion: #b31d28;
  --hljs-attr: #22863a;
  --hljs-operator: #d73a49;
}
</style>
