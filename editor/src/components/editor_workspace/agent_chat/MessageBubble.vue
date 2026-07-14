<!--
  Message bubble router.

  Usage:
  Matches the console chat rendering path: chat mode uses ChatBubble with
  collapsible thinking, tool mode uses ToolBubble with inline tool calls.
-->
<script setup lang="ts">
import ChatBubble from '@/components/editor_workspace/agent_chat/ChatBubble.vue'
import ToolBubble from '@/components/editor_workspace/agent_chat/ToolBubble.vue'
import { useSettingsStore } from '@/stores/settings'
import type { AgentChatMessage } from '@/stores/chat'

const props = defineProps<{
  message: AgentChatMessage
  isStreaming?: boolean
  userAvatar: string
  agentAvatar: string
  showAvatar?: boolean
  knowledgeSources?: Array<{source_uri: string; content: string}>
  citationMap?: Record<string, {source_uri: string; content: string}>
}>()

const settingsStore = useSettingsStore()
</script>

<template>
  <ChatBubble v-if="settingsStore.chatMode === 'chat'" v-bind="props" />
  <ToolBubble v-else v-bind="props" />
</template>
