<!--
  Code preview surface.

  Usage:
  Renders supported code files through highlight.js. EditorPane uses this for
  Preview/Split mode while CodeEditor.vue owns editing.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { hljs, isHighlightableLanguage } from './codeHighlight'

const props = defineProps<{
  content: string
  language: string
}>()

const highlightedHtml = computed(() => {
  const language = isHighlightableLanguage(props.language) ? props.language : 'plaintext'
  return hljs.highlight(props.content, { language }).value
})
</script>

<template>
  <article class="code-preview" :class="{ 'code-preview--markdown': language === 'markdown' }">
    <pre><code v-html="highlightedHtml"></code></pre>
  </article>
</template>

<style scoped>
.code-preview {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border: 0;
  border-radius: 0;
  background: var(--color-canvas);
}

.code-preview pre {
  min-width: max-content;
  margin: 0;
  padding: var(--space-12);
}

.code-preview code {
  color: var(--color-text);
  font-family: var(--font-code);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
}

.code-preview--markdown code {
  font-family: var(--font-text);
  font-size: calc(13px * var(--text-font-scale));
}
</style>
