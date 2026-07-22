<!--
  Code preview surface.

  Usage:
  Renders supported code files through highlight.js. EditorPane uses this for
  Preview/Split mode while CodeEditor.vue owns editing.
-->
<script setup lang="ts">
import { computed } from 'vue'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import cpp from 'highlight.js/lib/languages/cpp'
import csharp from 'highlight.js/lib/languages/csharp'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('cs', csharp)
hljs.registerLanguage('css', css)
hljs.registerLanguage('go', go)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('java', java)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('rs', rust)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('vue', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)

const props = defineProps<{
  content: string
  language: string
}>()

const highlightedHtml = computed(() => {
  const language = hljs.getLanguage(props.language) ? props.language : 'plaintext'
  return hljs.highlight(props.content, { language }).value
})
</script>

<template>
  <article class="code-preview">
    <pre><code v-html="highlightedHtml"></code></pre>
  </article>
</template>

<style scoped>
.code-preview {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
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
</style>
