<!--
  Agent chat message list.

  Usage:
  Displays streamed chat messages and keeps the scroll pinned to bottom unless
  the user scrolls upward to inspect history.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import LoaderCube from '@/components/editor_workspace/agent_chat/LoaderCube.vue'
import MessageBubble from '@/components/editor_workspace/agent_chat/MessageBubble.vue'
import { useAvatar } from '@/components/editor_workspace/agent_chat/useAvatar'
import { useChatStore } from '@/stores/chat'
import type { AgentChatMessage } from '@/stores/chat'

const chatStore = useChatStore()

const props = defineProps<{
  messages: AgentChatMessage[]
  isStreaming?: boolean
  mergeAssistants?: boolean
}>()

const { userAvatar, agentAvatar } = useAvatar()
const containerRef = ref<HTMLDivElement | null>(null)
const isPinnedToBottom = ref(true)

function mergeConsecutiveAssistants(messages: AgentChatMessage[]) {
  return messages.filter((message) => message.role !== 'system').reduce<AgentChatMessage[]>((acc, message) => {
    const previous = acc[acc.length - 1]
    if (message.role === 'assistant' && previous?.role === 'assistant') {
      const merged: AgentChatMessage = {
        ...previous,
        content: message.content || previous.content,
        node: message.node || previous.node,
        tool_calls: message.tool_calls?.length ? message.tool_calls : previous.tool_calls,
        trace: [...(previous.trace ?? []), ...(message.trace ?? [])],
      }
      acc[acc.length - 1] = merged
    } else {
      acc.push(message)
    }
    return acc
  }, [])
}

function mergeConsecutiveSameNode(messages: AgentChatMessage[]) {
  return messages.filter((message) => message.role !== 'system').reduce<AgentChatMessage[]>((acc, message) => {
    const previous = acc[acc.length - 1]
    if (message.role === 'assistant' && previous?.role === 'assistant' && previous.node === message.node) {
      const merged: AgentChatMessage = {
        ...previous,
        content: previous.content + message.content,
        tool_calls: [...(previous.tool_calls ?? []), ...(message.tool_calls ?? [])],
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
  return props.mergeAssistants ? mergeConsecutiveAssistants(base) : mergeConsecutiveSameNode(base)
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

function scrollToBottom() {
  const container = containerRef.value
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

function handleScroll() {
  isPinnedToBottom.value = isNearBottom()
}

function scheduleScrollIfNeeded() {
  const shouldAutoScroll = isPinnedToBottom.value || isNearBottom()
  void nextTick(() => {
    if (shouldAutoScroll) {
      scrollToBottom()
      isPinnedToBottom.value = true
    }
  })
}

function getLastMessageContent() {
  const last = props.messages[props.messages.length - 1]
  return last?.content ?? ''
}

function shouldShowAvatar(message: AgentChatMessage, index: number) {
  const previous = visibleMessages.value[index - 1]
  return message.role !== 'assistant' || index === 0 || previous?.role !== 'assistant'
}

watch(() => props.messages.length, scheduleScrollIfNeeded)
watch(getLastMessageContent, scheduleScrollIfNeeded)

onMounted(() => {
  scrollToBottom()
  isPinnedToBottom.value = true
})
</script>

<template>
  <div ref="containerRef" class="message-list" @scroll="handleScroll">
    <MessageBubble
      v-for="(message, index) in visibleMessages"
      :key="message.message_id ?? `${message.role}-${index}`"
      :message="message"
      :is-streaming="isStreaming && index === visibleMessages.length - 1"
      :user-avatar="userAvatar"
      :agent-avatar="agentAvatar"
      :show-avatar="shouldShowAvatar(message, index)"
      :knowledge-sources="message.role === 'assistant' ? chatStore.currentKnowledgeSources : []"
      :citation-map="message.role === 'assistant' ? chatStore.currentCitationMap : {}"
    />
    <div v-if="showThinkingBubble" class="thinking-row">
      <img :src="agentAvatar" class="thinking-avatar" alt="agent" />
      <LoaderCube />
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
  scrollbar-width: none;
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
  border: 1px solid var(--color-border);
  border-radius: 50%;
  object-fit: cover;
}

</style>
