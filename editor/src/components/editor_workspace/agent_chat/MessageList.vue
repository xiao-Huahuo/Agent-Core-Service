<!--
  Agent chat message list.

  Usage:
  Displays streamed chat messages and keeps the scroll pinned to bottom unless
  the user scrolls upward to inspect history.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import LoadingState from '@/components/common/LoadingState.vue'
import LoaderCube from '@/components/editor_workspace/agent_chat/LoaderCube.vue'
import FinalTurnSummary from '@/components/editor_workspace/agent_chat/FinalTurnSummary.vue'
import MessageBubble from '@/components/editor_workspace/agent_chat/MessageBubble.vue'
import { undoSessionChange } from '@/api/agentChanges'
import type { AgentChangeSnapshot } from '@/api/agentChanges'
import { useAvatar } from '@/components/editor_workspace/agent_chat/useAvatar'
import type { AgentChatMessage, SourceItem } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  messages: AgentChatMessage[]
  isStreaming?: boolean
  mergeAssistants?: boolean
  // 输入框上方悬浮小模型任务建议时,提高底部留白避免滚动底限遮住消息
  suggestionOverlay?: boolean
}>()

const emit = defineEmits<{
  'bottom-change': [isAtBottom: boolean]
}>()

const { userAvatar, agentAvatar } = useAvatar()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const containerRef = ref<HTMLDivElement | null>(null)
const isPinnedToBottom = ref(true)
const isThinkingActive = computed(() => Boolean(props.isStreaming))
const undoingSnapshotId = ref('')

function mergeConsecutiveSameNode(messages: AgentChatMessage[]) {
  return messages.filter((message) => message.role !== 'system').reduce<AgentChatMessage[]>((acc, message) => {
    const previous = acc[acc.length - 1]
    const isChildAgentEvent = message.node === 'child_agent' || previous?.node === 'child_agent'
    if (message.role === 'assistant' && previous?.role === 'assistant' && previous.node === message.node && !isChildAgentEvent) {
      const merged: AgentChatMessage = {
        ...previous,
        content: previous.content + message.content,
        tool_calls: [...(previous.tool_calls ?? []), ...(message.tool_calls ?? [])],
        metadata: { ...(previous.metadata ?? {}), ...(message.metadata ?? {}) },
        trace: [...(previous.trace ?? []), ...(message.trace ?? [])],
      }
      acc[acc.length - 1] = merged
    } else {
      acc.push(message)
    }
    return acc
  }, [])
}

const visibleMessages = computed(() => {
  const base = props.messages.filter((message) => message.role !== 'system')
  return mergeConsecutiveSameNode(base)
})

const showThinkingBubble = computed(() => {
  if (!props.isStreaming) {
    return false
  }
  const list = visibleMessages.value
  const last = list[list.length - 1]
  return !last || last.role !== 'assistant'
})

function isNearBottom() {
  const container = containerRef.value
  if (!container) {
    return true
  }
  return container.scrollHeight - container.scrollTop - container.clientHeight <= 24
}

function setPinnedToBottom(value: boolean) {
  if (isPinnedToBottom.value === value) {
    return
  }
  isPinnedToBottom.value = value
  emit('bottom-change', value)
}

function scrollToBottom(options: ScrollToOptions = {}) {
  const container = containerRef.value
  if (container) {
    container.scrollTo({
      top: container.scrollHeight,
      ...options,
    })
  }
}

function handleScroll() {
  setPinnedToBottom(isNearBottom())
}

function scheduleScrollIfNeeded() {
  const shouldAutoScroll = isPinnedToBottom.value || isNearBottom()
  void nextTick(() => {
    if (shouldAutoScroll) {
      scrollToBottom()
      setPinnedToBottom(true)
    }
  })
}

function getLastMessageContent() {
  const last = props.messages[props.messages.length - 1]
  return last?.content ?? ''
}

function shouldShowAvatar(message: AgentChatMessage, index: number) {
  if (message.role !== 'assistant') return true

  // A completed final reply keeps its avatar after streaming stops.
  if (isFinalAssistantAnswer(message, index)) return true

  // Keep one avatar on the currently active assistant item. Empty placeholders
  // no longer consume the avatar before a later tool result becomes visible.
  for (let nextIndex = index + 1; nextIndex < visibleMessages.value.length; nextIndex += 1) {
    const next = visibleMessages.value[nextIndex]
    if (next?.role === 'user') break
    if (next?.role === 'assistant') return false
  }
  return true
}

function hasCopyableAssistantContent(message: AgentChatMessage) {
  return message.role === 'assistant' && Boolean(message.content?.trim())
}

function isFinalAnswerNode(message: AgentChatMessage) {
  const node = String(message.node || message.metadata?.node || '')
  return node === 'agent' || node === 'error' || node === 'interrupted' || node === ''
}

function isCompletedAssistantContentMessage(message: AgentChatMessage) {
  return hasCopyableAssistantContent(message) && isFinalAnswerNode(message)
}

function isFinalAssistantAnswer(message: AgentChatMessage, index: number) {
  if (!hasCopyableAssistantContent(message)) {
    return false
  }

  // A turn ends at the next user message. Only the last assistant message
  // with visible content in that turn is the final answer shown to the user.
  for (let nextIndex = index + 1; nextIndex < visibleMessages.value.length; nextIndex += 1) {
    const nextMessage = visibleMessages.value[nextIndex]
    if (!nextMessage) {
      continue
    }
    if (nextMessage.role === 'user') {
      break
    }
    if (hasCopyableAssistantContent(nextMessage)) {
      return false
    }
  }
  return true
}

function shouldShowActions(message: AgentChatMessage, index: number) {
  if (message.role !== 'assistant') {
    return true
  }
  return !isThinkingActive.value
    && isCompletedAssistantContentMessage(message)
    && isFinalAssistantAnswer(message, index)
}

function asSourceMap(value: unknown): Record<string, SourceItem> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  const result: Record<string, SourceItem> = {}
  for (const [key, source] of Object.entries(value as Record<string, unknown>)) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) {
      continue
    }
    const record = source as Record<string, unknown>
    const sourceUri = typeof record.source_uri === 'string' ? record.source_uri : ''
    const content = typeof record.content === 'string' ? record.content : ''
    if (sourceUri || content) {
      result[key] = {
        source_uri: sourceUri,
        content,
        source: typeof record.source === 'string' ? record.source : undefined,
        title: typeof record.title === 'string' ? record.title : undefined,
      }
    }
  }
  return result
}

function extractCitationIds(content: string) {
  const ids: string[] = []
  const seen = new Set<string>()
  const pattern = /\[([A-Z]?\d+)\]/g
  let match = pattern.exec(content)
  while (match) {
    const id = match[1]
    if (id && !seen.has(id)) {
      ids.push(id)
      seen.add(id)
    }
    match = pattern.exec(content)
  }
  return ids
}

function citationMapForMessage(message: AgentChatMessage): Record<string, SourceItem> {
  if (isThinkingActive.value || !isCompletedAssistantContentMessage(message)) {
    return {}
  }
  return asSourceMap(message.metadata?.citation_map)
}

function knowledgeSourcesForMessage(message: AgentChatMessage): SourceItem[] {
  const citationMap = citationMapForMessage(message)
  const metadataUsed = Array.isArray(message.metadata?.used_citations)
    ? message.metadata.used_citations.filter((item): item is string => typeof item === 'string')
    : []
  const usedIds = metadataUsed.length > 0 ? metadataUsed : extractCitationIds(message.content)
  const sources: SourceItem[] = []
  const sourceIndexByUri = new Map<string, number>()
  for (const id of usedIds) {
    const source = citationMap[id]
    if (!source || !source.source_uri) {
      continue
    }
    const existingIndex = sourceIndexByUri.get(source.source_uri)
    if (existingIndex !== undefined) {
      const existing = sources[existingIndex]
      if (!existing) {
        continue
      }
      const existingIds = (existing.citation_id ?? '').split(',').map((item) => item.trim()).filter(Boolean)
      if (!existingIds.includes(id)) {
        existing.citation_id = [...existingIds, id].join(', ')
      }
      continue
    }
    sourceIndexByUri.set(source.source_uri, sources.length)
    sources.push({ ...source, citation_id: id })
  }
  return sources
}

function changeSnapshotForMessage(message: AgentChatMessage): AgentChangeSnapshot | null {
  const snapshot = message.metadata?.change_snapshot
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return null
  const record = snapshot as Partial<AgentChangeSnapshot>
  return typeof record.snapshot_id === 'string' && typeof record.session_id === 'string'
    ? record as AgentChangeSnapshot
    : null
}

/** Finds the finalized snapshot for an action message before the next user turn. */
function changeSnapshotForAction(index: number): AgentChangeSnapshot | null {
  for (let cursor = index + 1; cursor < visibleMessages.value.length; cursor += 1) {
    const candidate = visibleMessages.value[cursor]
    if (candidate?.role === 'user') break
    if (candidate) {
      const snapshot = changeSnapshotForMessage(candidate)
      if (snapshot) return snapshot
    }
  }
  return null
}

async function undoMessageChange(message: AgentChatMessage) {
  const snapshot = changeSnapshotForMessage(message)
  const sessionId = snapshot?.session_id
  const snapshotId = snapshot?.snapshot_id
  const userId = settingsStore.profile.userId
  if (typeof sessionId !== 'string' || typeof snapshotId !== 'string' || !userId) return
  undoingSnapshotId.value = snapshotId
  try {
    const result = await undoSessionChange(sessionId, snapshotId, userId)
    message.metadata = { ...(message.metadata ?? {}), change_snapshot: result.change_snapshot ?? snapshot }
  } finally {
    undoingSnapshotId.value = ''
  }
}

watch(() => props.messages.length, (newLen, oldLen) => {
  // 新提交 prompt（新增用户消息）时强制滚动到底部
  if (newLen > oldLen && oldLen > 0 && props.messages[newLen - 1]?.role === 'user') {
    void nextTick(() => {
      scrollToBottom()
      setPinnedToBottom(true)
    })
    return
  }
  scheduleScrollIfNeeded()
})
watch(getLastMessageContent, scheduleScrollIfNeeded)

onMounted(() => {
  scrollToBottom()
  setPinnedToBottom(true)
})

defineExpose({
  scrollToBottom,
})
</script>

<template>
  <div
    ref="containerRef"
    class="message-list"
    :class="{ 'with-suggestion-overlay': suggestionOverlay }"
    @scroll="handleScroll"
  >
    <template v-for="(message, index) in visibleMessages" :key="message.message_id ?? `${message.role}-${index}`">
      <MessageBubble
        :message="message"
        :is-streaming="isStreaming && index === visibleMessages.length - 1"
        :is-thinking-active="isThinkingActive"
        :user-avatar="userAvatar"
        :agent-avatar="agentAvatar"
        :show-avatar="shouldShowAvatar(message, index)"
        :show-actions="shouldShowActions(message, index)"
        :knowledge-sources="[]"
        :citation-map="message.role === 'assistant' ? citationMapForMessage(message) : {}"
        :change-snapshot="message.node === 'action' ? changeSnapshotForAction(index) : changeSnapshotForMessage(message)"
      />
      <FinalTurnSummary
        v-if="message.role === 'assistant' && isFinalAssistantAnswer(message, index) && !isThinkingActive"
        class="assistant-summary-offset"
        :sources="knowledgeSourcesForMessage(message)"
        :change-snapshot="changeSnapshotForMessage(message)"
        :undoing="undoingSnapshotId === changeSnapshotForMessage(message)?.snapshot_id"
        @undo="undoMessageChange(message)"
      />
    </template>
    <div v-if="showThinkingBubble" class="thinking-row">
      <img :src="agentAvatar" class="thinking-avatar" alt="agent" />
      <LoadingState label="Thinking" variant="Drive" :started-at-ms="chatStore.streamStartedAtMs" />
      <span class="thinking-spinner" aria-label="Preparing response"><LoaderCube /></span>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: var(--space-16);
  padding-bottom: 116px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
}

/* 任务建议悬浮在输入框上方(bottom: 输入框高 + 8px + 按钮高,单行约 142px,
   两行约 174px),把滚动底限提高到建议之上,避免最后一条消息被建议遮挡 */
.message-list.with-suggestion-overlay {
  padding-bottom: 176px;
}

.message-list::-webkit-scrollbar {
  display: none;
}

.thinking-row {
  display: flex;
  align-items: center;
  align-self: flex-start;
  gap: var(--space-6);
  padding: var(--space-8) 0;
}

.thinking-avatar {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  object-fit: cover;
}

.thinking-spinner {
  display: inline-flex;
  font-size: 0.55em;
}

/* Final cards share the assistant text column rather than the avatar column. */
.assistant-summary-offset {
  margin-left: calc(36px + var(--space-8));
}

</style>
