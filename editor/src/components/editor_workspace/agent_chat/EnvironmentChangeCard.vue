<!--
  Agent environment and change card.

  Usage:
  Reuses the Agent sidebar-card hierarchy to surface the current session's
  durable change summary, Git environment and aggregated source references.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { fetchSessionChanges } from '@/api/agentChanges'
import { fetchSessionState, saveSessionEnvironment } from '@/api/session'
import { fetchGitHistory, fetchGitStatus } from '@/api/git'
import type { SourceItem } from '@/stores/chat'

defineOptions({ name: 'EnvironmentChangeCard' })

const props = defineProps<{ sessionId: string; userId: string; sources: SourceItem[] }>()
const emit = defineEmits<{ close: []; showChanges: [snapshot: NonNullable<typeof snapshot.value>] }>()
const snapshot = ref<Awaited<ReturnType<typeof fetchSessionChanges>>['change_snapshot']>(null)
const branch = ref('—')
const commit = ref('—')
const commitTime = ref('—')
const sourceCount = computed(() => new Set(props.sources.map((source) => source.source_uri)).size)

async function load() {
  if (!props.sessionId || !props.userId) return
  const [changes, status, history, sessionState] = await Promise.allSettled([
    fetchSessionChanges(props.sessionId), fetchGitStatus(props.userId), fetchGitHistory(props.userId, 1),
    fetchSessionState(props.sessionId),
  ])
  if (changes.status === 'fulfilled') snapshot.value = changes.value.change_snapshot
  if (!snapshot.value && sessionState.status === 'fulfilled') {
    const saved = sessionState.value.session_state?.change_snapshot
    if (saved && typeof saved === 'object') snapshot.value = saved as typeof snapshot.value
  }
  const savedEnvironment = sessionState.status === 'fulfilled'
    ? sessionState.value.session_state?.environment as Record<string, string> | undefined
    : undefined
  if (savedEnvironment) {
    branch.value = savedEnvironment.branch || '—'
    commit.value = savedEnvironment.commit || '—'
    commitTime.value = savedEnvironment.commit_time || '—'
  }
  if (status.status === 'fulfilled' && !savedEnvironment) branch.value = status.value.current_branch || '—'
  if (history.status === 'fulfilled') {
    const item = history.value.history?.[0]
    if (!savedEnvironment) {
      commit.value = item?.summary || '—'
      commitTime.value = item?.date || '—'
    }
  }
  if (!savedEnvironment && status.status === 'fulfilled') {
    void saveSessionEnvironment(props.sessionId, {
      branch: branch.value,
      commit: commit.value,
      commit_time: commitTime.value,
    })
  }
}

watch(() => props.sessionId, () => void load(), { immediate: true })
onMounted(() => void load())
onMounted(() => window.addEventListener('agent-change-updated', handleChangeUpdated as EventListener))
onBeforeUnmount(() => window.removeEventListener('agent-change-updated', handleChangeUpdated as EventListener))

/** Applies the current run snapshot immediately after a file patch succeeds. */
function handleChangeUpdated(event: CustomEvent<typeof snapshot.value>) {
  const incoming = event.detail
  if (incoming?.session_id === props.sessionId) snapshot.value = incoming
}
</script>

<template>
  <div class="environment-card">
    <header><span><IcIcon name="terminal" :size="15" /> 环境与变更</span><button type="button" @click="emit('close')"><IcIcon name="close" :size="15" /></button></header>
    <button class="change-row" type="button" :disabled="!snapshot" @click="snapshot && emit('showChanges', snapshot)">
      <span>变更</span><strong>+{{ snapshot?.additions ?? 0 }}</strong><em>-{{ snapshot?.deletions ?? 0 }}</em><IcIcon name="chevron-right" :size="14" />
    </button>
    <dl><div><dt>分支</dt><dd>{{ branch }}</dd></div><div><dt>上次提交</dt><dd>{{ commit }}</dd></div><div><dt>提交时间</dt><dd>{{ commitTime }}</dd></div></dl>
    <details><summary>来源 <span>{{ sourceCount }}</span><IcIcon name="chevron-down" :size="13" /></summary><ul><li v-for="source in sources" :key="source.source_uri">{{ source.title || source.source_uri }}</li><li v-if="!sources.length">本会话暂无引用</li></ul></details>
  </div>
</template>

<style scoped>
.environment-card { padding: var(--space-12); color: var(--color-text-secondary); font-size: calc(12px * var(--font-scale)); }
header,.change-row,dl div,summary { display:flex; align-items:center; justify-content:space-between; gap:var(--space-8); } header { margin-bottom:var(--space-10); color:var(--color-text-primary); font-weight:650; } header span{display:flex;gap:6px;align-items:center} button { border:0;background:transparent;color:inherit;cursor:pointer } .change-row{width:100%;padding:var(--space-8);border-radius:var(--radius-sm);background:var(--color-primary-soft);text-align:left}.change-row:disabled{opacity:.55;cursor:default}.change-row strong{margin-left:auto;color:var(--color-success)}.change-row em{font-style:normal;color:var(--color-danger)}dl{margin:var(--space-10) 0}dl div{padding:5px 0}dt{color:var(--color-text-tertiary)}dd{margin:0;max-width:65%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}summary{cursor:pointer;list-style:none}summary span{margin-left:auto}ul{margin:var(--space-6) 0 0;padding:0;list-style:none;max-height:100px;overflow:auto}li{padding:4px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--color-text-tertiary)}
</style>
