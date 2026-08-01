<!--
  Message bubble router.

  Usage:
  Matches the console chat rendering path: chat mode uses ChatBubble with
  collapsible thinking, tool mode uses ToolBubble with inline tool calls.
-->
<script setup lang="ts">
import { computed } from 'vue'

import ChatBubble from '@/components/editor_workspace/agent_chat/ChatBubble.vue'
import ChildAgentEventInline from '@/components/editor_workspace/agent_chat/ChildAgentEventInline.vue'
import ToolBubble from '@/components/editor_workspace/agent_chat/ToolBubble.vue'
import { useSettingsStore } from '@/stores/settings'
import type { AgentChatMessage } from '@/stores/chat'

const props = defineProps<{
  message: AgentChatMessage
  isStreaming?: boolean
  isThinkingActive?: boolean
  userAvatar: string
  agentAvatar: string
  showAvatar?: boolean
  showActions?: boolean
  knowledgeSources?: Array<{source_uri: string; content: string}>
  citationMap?: Record<string, {source_uri: string; content: string}>
}>()

const settingsStore = useSettingsStore()
const childAgentEvent = computed(() => {
  const value = props.message.metadata?.child_agent_event
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined
})
</script>

<template>
  <ChildAgentEventInline
    v-if="message.role === 'assistant' && message.node === 'child_agent'"
    :event="childAgentEvent"
  />
  <ChatBubble v-else-if="settingsStore.chatMode === 'chat'" v-bind="props" />
  <ToolBubble v-else v-bind="props" />
</template>
