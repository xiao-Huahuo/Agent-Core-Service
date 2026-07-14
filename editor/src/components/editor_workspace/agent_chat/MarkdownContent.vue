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

// Register marked extension for citation anchors [N]
const citationExtension = {
  name: 'citation',
  level: 'inline' as const,
  start(src: string) { return src.indexOf('[') },
  tokenizer(src: string) {
    const match = src.match(/^\[(\d+)\]/)
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

function handleClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const citation = target.closest('.citation-anchor') as HTMLElement | null
  if (!citation || !props.onNavigateSource) return
  const idx = citation.getAttribute('data-citation-idx')
  if (!idx) return
  const map = props.citationMap
  if (!map || !map[idx]) return
  props.onNavigateSource(map[idx].source_uri)
}

async function highlightCodeBlocks() {
  await nextTick()
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

watch(sanitizedHtml, () => void highlightCodeBlocks(), { immediate: true })
</script>

<template>
  <div ref="contentRef" class="markdown-body" v-html="sanitizedHtml"></div>
</template>

<style scoped>
.markdown-body {
  color: var(--color-text-primary);
  font-family: var(--font-chat);
  font-size: var(--font-size-sm);
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
  min-width: 16px;
  height: 14px;
  padding: 0 3px;
  border-radius: 3px;
  background: var(--color-accent-muted);
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 650;
  cursor: pointer;
  vertical-align: super;
  line-height: 1;
  transition:
    background var(--transition-fast),
    opacity var(--transition-fast);
}

.markdown-body :deep(.citation-anchor:hover) {
  background: var(--color-accent);
  color: #ffffff;
  opacity: 0.85;
}
</style>
