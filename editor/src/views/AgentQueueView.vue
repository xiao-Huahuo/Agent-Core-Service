<!-- Page-level Kanban board for durable, independently running Agent tasks. -->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AgentQueueTaskCard from '@/components/agent_queue/AgentQueueTaskCard.vue'
import AgentQueueTaskDialog from '@/components/agent_queue/AgentQueueTaskDialog.vue'
import QueueDropdown from '@/components/agent_queue/QueueDropdown.vue'
import { continueQueueTask, createQueueTask, deleteQueueTask, transitionQueueTask, updateQueueSettings, updateQueueTask, type AgentQueuePriority, type AgentQueueTask } from '@/api/agentQueue'
import { deleteAgentAttachment, uploadAgentAttachment } from '@/api/agent'
import { createSession, deleteSession } from '@/api/session'
import IcIcon from '@/components/common/IcIcon.vue'
import { useAgentQueueStore } from '@/stores/agentQueue'
import { useSettingsStore } from '@/stores/settings'
import type { AgentUploadedAttachment } from '@/stores/chat'

const settings = useSettingsStore(), queue = useAgentQueueStore()
const historyMode = ref(false), dialogOpen = ref(false), selected = ref<AgentQueueTask | null>(null), attachments = ref<AgentUploadedAttachment[]>([]), uploading = ref(false)
const pageSwitchRef = ref<HTMLElement | null>(null)
const pageSliderStyle = ref({ width: '0px', left: '0px' })
const concurrencyValue = ref('5')
const concurrencyOptions = Array.from({ length: 10 }, (_, index) => ({ value: String(index + 1), label: String(index + 1) }))
let pollId: number | null = null
const userId = () => settings.profile.userId
async function refresh() { await queue.load(userId(), historyMode.value); concurrencyValue.value = String(queue.maxConcurrency) }
/** 将滑块对齐当前按钮的真实尺寸，避免不同文案宽度造成错位。 */
function updatePageSlider() {
  nextTick(() => {
    const switcher = pageSwitchRef.value
    const activeButton = switcher?.querySelector('.queue-page-button.active') as HTMLElement | null
    if (!activeButton) return
    pageSliderStyle.value = { width: `${activeButton.offsetWidth}px`, left: `${activeButton.offsetLeft}px` }
  })
}
/** 切换看板与历史，并同步胶囊滑块位置。 */
function switchPage(nextHistoryMode: boolean) { historyMode.value = nextHistoryMode; void refresh(); updatePageSlider() }
function openNew() { selected.value = null; attachments.value = []; sessionForDraft.value = ''; dialogOpen.value = true }
function openTask(task: AgentQueueTask) { selected.value = task; attachments.value = task.attachments; dialogOpen.value = true }
async function upload(files: File[]) { if (!files.length) return; uploading.value = true; try { if (!sessionForDraft.value) sessionForDraft.value = (await createSession(userId(), '待执行任务')).session_id; for (const file of files) attachments.value.push((await uploadAgentAttachment(userId(), sessionForDraft.value, file)).attachment) } finally { uploading.value = false } }
const sessionForDraft = ref('')
async function create(prompt: string, priority: AgentQueuePriority) { let sessionId = sessionForDraft.value; if (!sessionId) sessionId = (await createSession(userId(), prompt.slice(0, 80))).session_id; await createQueueTask({ user_id: userId(), prompt, priority, attachments: attachments.value, session_id: sessionId }); sessionForDraft.value = ''; dialogOpen.value = false; await refresh() }
async function closeDialog() { if (!selected.value && sessionForDraft.value) await deleteSession(sessionForDraft.value); sessionForDraft.value = ''; dialogOpen.value = false }
async function removeAttachment(item: AgentUploadedAttachment) { const sessionId = selected.value?.session_id || sessionForDraft.value; if (sessionId) await deleteAgentAttachment(userId(), sessionId, item.attachment_id); attachments.value = attachments.value.filter(entry => entry.attachment_id !== item.attachment_id) }
async function transition(task: AgentQueueTask, status: 'confirmed' | 'terminated') { await transitionQueueTask(task.task_id, userId(), status); dialogOpen.value = false; await refresh() }
async function update(task: AgentQueueTask, prompt: string, priority: AgentQueuePriority) { await updateQueueTask(task.task_id, { user_id: userId(), prompt, priority, attachments: attachments.value }); dialogOpen.value = false; await refresh() }
async function removeTask(task: AgentQueueTask) { await deleteQueueTask(task.task_id, userId()); dialogOpen.value = false; await refresh() }
async function continueTask(task: AgentQueueTask, prompt: string) { await continueQueueTask(task.task_id, { user_id: userId(), prompt, attachments: attachments.value }); dialogOpen.value = false; await refresh() }
async function saveConcurrency(value: string) { await updateQueueSettings(userId(), Number(value)); await refresh() }
onMounted(() => { void refresh(); updatePageSlider(); pollId = window.setInterval(() => void refresh(), 1500) })
onBeforeUnmount(() => { if (pollId !== null) window.clearInterval(pollId) })
</script>
<template><section class="agent-queue-view"><header class="queue-topbar"><div ref="pageSwitchRef" class="queue-page-switch" aria-label="任务队列页面"><span class="queue-page-slider" :style="pageSliderStyle" aria-hidden="true"></span><button class="queue-page-button" :class="{ active: !historyMode }" type="button" @click="switchPage(false)"><IcIcon name="checklist" :size="17" /><span>Issue 看板</span></button><button class="queue-page-button" :class="{ active: historyMode }" type="button" @click="switchPage(true)"><IcIcon name="history" :size="17" /><span>历史</span></button></div><span class="queue-toolbar-separator" aria-hidden="true"></span><div class="queue-toolbar-spacer"></div><label class="queue-concurrency"><span>最大并行</span><QueueDropdown v-model="concurrencyValue" aria-label="最大并行任务数" :options="concurrencyOptions" @update:model-value="saveConcurrency" /></label><span class="queue-toolbar-separator" aria-hidden="true"></span><button class="queue-new-task" type="button" @click="openNew"><IcIcon name="add" :size="17" /><span>新建任务</span></button></header>
<Transition name="queue-switch" mode="out-in"><main v-if="!historyMode" key="board" class="queue-board"><div class="queue-lane"><h2 class="queue-column-title pending">等待认领 <small>{{ queue.pending.length }}</small></h2><section><TransitionGroup name="queue-card" tag="div" class="queue-column"><AgentQueueTaskCard v-for="task in queue.pending" :key="task.task_id" :task="task" @select="openTask" @remove-task="removeTask" /></TransitionGroup></section></div><div class="queue-lane"><h2 class="queue-column-title running">处理中 <small>{{ queue.running.length }}</small></h2><section><TransitionGroup name="queue-card" tag="div" class="queue-column"><AgentQueueTaskCard v-for="task in queue.running" :key="task.task_id" :task="task" @select="openTask" @terminate="transition($event, 'terminated')" /></TransitionGroup></section></div><div class="queue-lane"><h2 class="queue-column-title review">等待确认 <small>{{ queue.review.length }}</small></h2><section><TransitionGroup name="queue-card" tag="div" class="queue-column"><AgentQueueTaskCard v-for="task in queue.review" :key="task.task_id" :task="task" @select="openTask" @confirm="transition($event, 'confirmed')" /></TransitionGroup></section></div></main><main v-else key="history" class="history-list"><div class="queue-lane"><h2 class="queue-column-title confirmed">已确认 <small>{{ queue.history.filter(item => item.status === 'confirmed').length }}</small></h2><section><div class="queue-column"><AgentQueueTaskCard v-for="task in queue.history.filter(item => item.status === 'confirmed')" :key="task.task_id" :task="task" @select="openTask" /></div></section></div><div class="queue-lane"><h2 class="queue-column-title terminated">已终止 <small>{{ queue.history.filter(item => item.status === 'terminated').length }}</small></h2><section><div class="queue-column"><AgentQueueTaskCard v-for="task in queue.history.filter(item => item.status === 'terminated')" :key="task.task_id" :task="task" @select="openTask" /></div></section></div></main></Transition>
<AgentQueueTaskDialog :open="dialogOpen" :task="selected" :attachments="attachments" :uploading="uploading" @close="closeDialog" @upload="upload" @remove="removeAttachment" @create="create" @update="update" @continue="continueTask" @remove-task="removeTask" @terminate="transition($event, 'terminated')" /></section></template>
<style scoped>
.agent-queue-view { display:flex; flex:1; min-height:0; flex-direction:column; overflow:auto; background:var(--color-canvas); }
.queue-topbar { display:flex; align-items:center; gap:var(--space-8); flex:0 0 auto; min-height:44px; padding:var(--space-8) var(--space-12); background:var(--color-panel-bg); font-size:calc(12px * var(--font-scale)); }
.queue-page-switch { position:relative; display:inline-grid; grid-template-columns:repeat(2, auto); align-items:center; gap:var(--space-2); padding:2px; border:1px solid var(--color-border); border-radius:999px; background:var(--color-canvas); }
.queue-page-slider { position:absolute; top:2px; height:calc(100% - 4px); border-radius:999px; background:var(--color-primary-softer); transition:left 250ms ease, width 250ms ease; pointer-events:none; }
.queue-page-button { position:relative; z-index:1; display:inline-flex; align-items:center; justify-content:center; gap:var(--space-6); height:28px; padding:0 var(--space-8); border:0; border-radius:999px; background:transparent; color:var(--color-text-secondary); font:inherit; font-size:calc(12px * var(--font-scale)); line-height:1; cursor:pointer; outline:none; }
.queue-page-button > span { display:block; line-height:1; }
.queue-page-button:hover,.queue-page-button.active { color:var(--color-primary); }
.queue-toolbar-separator { display:block; width:1px; height:22px; margin:0 var(--space-2); background:var(--color-border); }
.queue-toolbar-spacer { flex:1 1 auto; min-width:0; }
.queue-concurrency { display:inline-flex; align-items:center; gap:var(--space-6); min-height:28px; padding:0 var(--space-8); border:1px solid var(--color-border); border-radius:999px; background:var(--color-canvas); color:var(--color-text-secondary); font:inherit; font-size:calc(12px * var(--font-scale)); }
.queue-concurrency :deep(.queue-select) { width:30px; }
.queue-new-task { display:inline-flex; align-items:center; justify-content:center; gap:var(--space-6); width:auto; height:28px; padding:0 var(--space-8); border:0; border-radius:var(--radius-sm); background:transparent; color:var(--color-text-secondary); font:inherit; font-size:calc(12px * var(--font-scale)); cursor:pointer; }
.queue-new-task:hover { background:var(--color-primary-softer); color:var(--color-primary); }
.queue-board,.history-list { display:grid; flex:1 1 auto; min-height:0; margin:20px 24px 24px; }.queue-board { grid-template-columns:repeat(3,minmax(220px,1fr)); gap:16px; }.history-list { grid-template-columns:repeat(2,minmax(260px,1fr)); gap:16px; }.queue-lane { display:flex; min-width:0; min-height:0; flex-direction:column; gap:var(--space-10); }.queue-lane>section { display:flex; min-height:0; flex:1 1 auto; flex-direction:column; padding:var(--space-8); }.queue-column-title { display:flex; flex:0 0 auto; align-items:center; justify-content:space-between; width:100%; min-height:32px; margin:0; padding:0 var(--space-12); border-radius:999px; font:650 calc(13px * var(--font-scale)) var(--font-ui); }.queue-column-title small { font:650 calc(11px * var(--font-scale)) var(--font-ui); opacity:.78; }.queue-column-title.pending { background:var(--color-primary-softer); color:var(--color-primary); }.queue-column-title.running { background:color-mix(in srgb, var(--color-warning) 18%, transparent); color:var(--color-warning); }.queue-column-title.review { background:color-mix(in srgb, var(--color-success) 16%, transparent); color:var(--color-success); }.queue-column-title.confirmed { background:color-mix(in srgb, var(--color-success) 16%, transparent); color:var(--color-success); }.queue-column-title.terminated { background:color-mix(in srgb, var(--color-danger) 14%, transparent); color:var(--color-danger); }.queue-column { display:grid; flex:1 1 auto; min-height:0; align-content:start; gap:var(--space-12); padding:4px; margin:-4px; overflow:auto; }.queue-card-enter-active,.queue-card-leave-active { transition:opacity 180ms ease, transform 180ms ease; }.queue-card-enter-from,.queue-card-leave-to { opacity:0; transform:translateY(8px); }.queue-switch-enter-active,.queue-switch-leave-active { transition:opacity 160ms ease; }.queue-switch-enter-from,.queue-switch-leave-to { opacity:0; } @media (max-width:760px) { .queue-board,.history-list { grid-template-columns:1fr; }.queue-topbar { flex-wrap:wrap; }.queue-toolbar-spacer { display:none; }.queue-concurrency { margin-left:auto; } }
.queue-lane > section {
  border: 0;
  border-radius: 28px;
  background: var(--color-surface);
  box-shadow: 0 0 0 4px var(--library-form-ring);
}
</style>
