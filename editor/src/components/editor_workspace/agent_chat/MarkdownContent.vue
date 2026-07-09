<!--
  Markdown content renderer for editor Agent chat.

  Usage:
  Parses assistant Markdown responses with marked, sanitizes with DOMPurify,
  and highlights code blocks after Vue patches the DOM.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
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

const props = defineProps<{
  content: string
  isStreaming?: boolean
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
  return DOMPurify.sanitize(marked.parse(stripHtml(props.content), { async: false }) as string)
})

async function highlightCodeBlocks() {
  await nextTick()
  contentRef.value?.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block as HTMLElement)
  })
}

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
</style>
