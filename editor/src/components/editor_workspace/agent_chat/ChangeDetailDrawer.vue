<!-- Local Agent patch detail drawer with compact three-line context. -->
<script setup lang="ts">
import { computed } from 'vue'
import IcIcon from '@/components/common/IcIcon.vue'
import type { AgentChangeSnapshot } from '@/api/agentChanges'

defineOptions({ name: 'ChangeDetailDrawer' })
const props = defineProps<{ snapshot: AgentChangeSnapshot | null }>()
const emit = defineEmits<{ close: [] }>()
const files = computed(() => props.snapshot?.files ?? [])

/** Builds the smallest readable hunk: three unchanged lines around the edited rows. */
function hunkLines(edit: AgentChangeSnapshot['edits'][number]) {
  const before = (edit.before ?? '').split('\n')
  const after = edit.after.split('\n')
  let prefix = 0
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix += 1
  let suffix = 0
  while (
    suffix < before.length - prefix
    && suffix < after.length - prefix
    && before[before.length - 1 - suffix] === after[after.length - 1 - suffix]
  ) suffix += 1
  const beforeEnd = before.length - suffix
  const afterEnd = after.length - suffix
  return [
    ...after.slice(Math.max(0, prefix - 3), prefix).map((text) => ({ text, kind: 'context' })),
    ...before.slice(prefix, beforeEnd).map((text) => ({ text, kind: 'removed' })),
    ...after.slice(prefix, afterEnd).map((text) => ({ text, kind: 'added' })),
    ...after.slice(afterEnd, afterEnd + 3).map((text) => ({ text, kind: 'context' })),
  ]
}
</script>

<template>
  <aside v-if="snapshot" class="change-detail" aria-label="变更明细">
    <header><span>变更明细</span><button type="button" @click="emit('close')"><IcIcon name="close" :size="15" /></button></header>
    <section v-for="file in files" :key="file.path"><div class="file-head"><span>{{ file.path }}</span><b>+{{ file.additions }}</b><i>-{{ file.deletions }}</i></div><article v-for="(edit, index) in file.edits" :key="index"><pre><code v-for="(line, lineIndex) in hunkLines(edit)" :key="lineIndex" :class="line.kind">{{ line.text || ' ' }}</code></pre></article></section>
  </aside>
</template>

<style scoped>
.change-detail{flex:0 0 min(390px,36vw);min-width:0;padding:var(--space-10);overflow:auto;border-left:1px solid var(--color-border);background:var(--color-surface-raised);font-size:calc(11px * var(--font-scale))}header,.file-head{display:flex;align-items:center;gap:var(--space-8)}header{justify-content:space-between;margin-bottom:var(--space-10);color:var(--color-text-primary);font-weight:650}button{border:0;background:transparent;color:inherit;cursor:pointer}section{margin-bottom:var(--space-12)}.file-head{padding:5px 0;color:var(--color-text-secondary)}.file-head span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-head b{margin-left:auto;color:var(--color-success)}.file-head i{font-style:normal;color:var(--color-danger)}article{margin-top:var(--space-6);overflow:hidden;border-radius:var(--radius-sm)}pre{margin:0;padding:var(--space-6);font-family:var(--font-code);white-space:pre-wrap;word-break:break-word}code{display:block;min-height:1.6em;padding:0 var(--space-6);margin:0 calc(var(--space-6) * -1);color:var(--color-text-secondary)}code.removed{background:color-mix(in srgb,var(--color-danger) 16%,transparent)}code.added{background:color-mix(in srgb,var(--color-primary) 16%,transparent)}
</style>
