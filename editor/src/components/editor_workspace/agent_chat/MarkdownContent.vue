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
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

import { useWorkspaceStore } from '@/stores/workspace'
import type { SourceItem } from '@/stores/chat'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('css', css)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('md', markdown)
hljs.registerLanguage('py', python)
hljs.registerLanguage('yml', yaml)

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

const contentRef = ref<HTMLDivElement | null>(null)
const workspaceStore = useWorkspaceStore()

function stripHtml(value: string): string {
  const container = document.createElement('div')
  let text = value
  for (let index = 0; index < 10; index += 1) {
    container.innerHTML = text
    if (container.textContent === text) {
      break
    }
    text = container.textContent ?? ''
  }
  return text
}

const sanitizedHtml = computed(() => {
  // Allow citation-anchor class and data-citation-idx attribute
  const purifyConfig = {
    ALLOWED_ATTR: ['data-citation-idx', 'class'],
    ADD_TAGS: ['sup'],
  }
  return DOMPurify.sanitize(
    marked.parse(stripHtml(props.content), { async: false }) as string,
    purifyConfig,
  )
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
  contentRef.value?.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block as HTMLElement)
  })
}

onMounted(() => {
  contentRef.value?.addEventListener('click', handleClick)
})

onUnmounted(() => {
  contentRef.value?.removeEventListener('click', handleClick)
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
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-weight: 650;
  line-height: var(--line-height-tight);
}

.markdown-body :deep(h1) { font-size: var(--font-size-xl); }
.markdown-body :deep(h2) { font-size: var(--font-size-lg); }
.markdown-body :deep(h3) { font-size: var(--font-size-md); }

.markdown-body :deep(code) {
  padding: 1px 4px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-bg-muted);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.markdown-body :deep(pre) {
  margin: var(--space-8) 0;
  padding: var(--space-12);
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-bg-muted);
}

.markdown-body :deep(pre code) {
  padding: 0;
  border: 0;
  background: transparent;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-8) 0;
  padding-left: var(--space-24);
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
  font-family: var(--font-mono);
  font-size: 9px;
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
</style>
