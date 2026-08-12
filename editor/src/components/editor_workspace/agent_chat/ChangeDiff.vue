<!--
  Shared Agent change diff renderer.

  Usage:
  Renders the same compact hunk in tool-call previews and the change drawer.
  Complete file versions allow real file line numbers. Partial live previews
  intentionally omit line numbers rather than presenting fabricated offsets.
-->
<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'ChangeDiff' })

const props = withDefaults(defineProps<{ before?: string | null; after: string; showLineNumbers?: boolean }>(), { showLineNumbers: true })

/** Produces a compact context hunk with one visible line number per row. */
const lines = computed(() => {
  const before = (props.before ?? '').split('\n')
  const after = props.after.split('\n')
  let prefix = 0
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix += 1
  let suffix = 0
  while (suffix < before.length - prefix && suffix < after.length - prefix && before[before.length - 1 - suffix] === after[after.length - 1 - suffix]) suffix += 1

  const contextStart = Math.max(0, prefix - 3)
  const result: Array<{ text: string; kind: 'context' | 'removed' | 'added'; line: number }> = []
  let oldLine = contextStart + 1
  let newLine = contextStart + 1
  for (const text of after.slice(contextStart, prefix)) result.push({ text, kind: 'context', line: newLine++ }), oldLine++
  for (const text of before.slice(prefix, before.length - suffix)) result.push({ text, kind: 'removed', line: oldLine++ })
  for (const text of after.slice(prefix, after.length - suffix)) result.push({ text, kind: 'added', line: newLine++ })
  for (const text of after.slice(after.length - suffix, after.length - suffix + 3)) result.push({ text, kind: 'context', line: newLine++ }), oldLine++
  return result
})
</script>

<template>
  <div class="change-diff" :class="{ 'has-line-numbers': showLineNumbers }"><div v-for="(line, index) in lines" :key="index" class="diff-line" :class="line.kind"><span v-if="showLineNumbers" class="line-number">{{ line.line }}</span><span class="line-text">{{ line.text || ' ' }}</span></div></div>
</template>

<style scoped>
.change-diff{margin:0;padding:var(--space-6) 0;overflow:auto;background:var(--color-code-bg);color:var(--color-text-primary);font-family:var(--font-chat);font-size:calc(12px * var(--font-scale));line-height:var(--line-height-relaxed);white-space:pre-wrap;word-break:break-word}.diff-line{display:block;min-height:var(--line-height-relaxed);font:inherit}.change-diff.has-line-numbers .diff-line{display:grid;grid-template-columns:48px minmax(0,1fr)}.line-number{padding:0 var(--space-8);color:var(--color-text-tertiary);font:inherit;text-align:right;user-select:none}.line-text{display:block;min-width:0;padding:0 var(--space-8);font:inherit;white-space:pre-wrap}.removed{background:rgba(235,36,99,.16)}.added{background:rgb(36 120 235 / 16%)}
</style>
