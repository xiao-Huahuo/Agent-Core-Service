<!--
  Final turn summary.

  Usage:
  Renders the persistent end-of-turn container below one completed assistant
  answer. Code-change statistics will be supplied by the change snapshot API;
  citations live here instead of being repeated beneath the response bubble.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import KnowledgeSources from '@/components/editor_workspace/agent_chat/KnowledgeSources.vue'
import type { AgentChangeSnapshot } from '@/api/agentChanges'
import type { SourceItem } from '@/stores/chat'

defineOptions({ name: 'FinalTurnSummary' })

const emit = defineEmits<{ undo: [] }>()

defineProps<{
  sources: SourceItem[]
  changeSnapshot?: AgentChangeSnapshot | null
  undoing?: boolean
}>()
</script>

<template>
  <section v-if="sources.length || changeSnapshot" class="final-turn-summary" aria-label="本轮结果">
    <p class="summary-title">本轮结果</p>
    <div v-if="changeSnapshot" class="change-summary">
      <span class="change-label">已编辑 {{ changeSnapshot.files.length }} 个文件</span>
      <span class="change-add">+{{ changeSnapshot.additions }}</span>
      <span class="change-remove">-{{ changeSnapshot.deletions }}</span>
      <button
        v-if="!changeSnapshot.is_undone"
        class="undo-button"
        type="button"
        :disabled="undoing"
        @click="emit('undo')"
      >
        <IcIcon name="undo" :size="13" />
        {{ undoing ? '撤销中' : '撤销' }}
      </button>
      <span v-else class="undo-done">已撤销</span>
    </div>
    <KnowledgeSources :sources="sources" />
  </section>
</template>

<style scoped>
.final-turn-summary {
  width: min(100%, 760px);
  margin: 2px 0 var(--space-12);
  padding: var(--space-10) var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
}

.summary-title {
  margin: 0 0 var(--space-6);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
}

.change-summary {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: 28px;
  margin-bottom: var(--space-8);
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.change-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.change-add { color: var(--color-success); }
.change-remove { color: var(--color-danger); }

.undo-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 3px 6px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  font: inherit;
  cursor: pointer;
}

.undo-button:hover:not(:disabled) {
  background: var(--color-primary-soft);
  color: var(--color-text-primary);
}

.undo-button:disabled { cursor: default; opacity: 0.6; }
.undo-done { margin-left: auto; color: var(--color-text-tertiary); }
</style>
