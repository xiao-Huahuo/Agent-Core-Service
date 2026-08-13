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
import type { AgentChangeSnapshot } from '@/api/agentChanges'
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
  changeSnapshot?: AgentChangeSnapshot | null
}>()

const settingsStore = useSettingsStore()
const childAgentEvent = computed(() => {
  const value = props.message.metadata?.child_agent_event
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined
})

// 子 Agent 完成后主 Agent 被自动唤起的系统提示消息,渲染为独立唤醒条而非用户气泡
const isWakeupMessage = computed(() => {
  return props.message.role === 'user' && props.message.metadata?.wakeup === true
})
</script>

<template>
  <div v-if="childAgentEvent" class="child-agent-event-row">
    <span class="child-agent-event-avatar-slot" aria-hidden="true"></span>
    <ChildAgentEventInline :event="childAgentEvent" />
  </div>
  <div v-else-if="isWakeupMessage" class="system-wakeup-strip" role="status" aria-label="子任务完成提醒">
    <svg class="system-wakeup-icon" xmlns="http://www.w3.org/2000/svg" height="14px" viewBox="0 -960 960 960" width="14px" fill="currentColor">
      <path d="M200-120q-33 0-56.5-23.5T120-200v-440q0-33 23.5-56.5T200-720h160q-14-18-21-39t-7-41q0-66 47-113t113-47q57 0 98.5 34t56.5 82q11 28 14.5 52t3.5 32h95q33 0 56.5 23.5T840-640v440q0 33-23.5 56.5T760-120H200Zm0-80h560v-440H200v440Zm100-280h120v-40H300v40Zm120 120h120v-40H420v40Zm120-120h120v-40H540v40Zm60-160q0-23-4-45t-13-41q-9-19-25.5-30.5T531-728q-20-8-39-1.5T461-697q-2 4-2 8t2 9q5 14 8.5 24t8.5 16h123Z"/>
    </svg>
    <span>子任务完成，主Agent继续</span>
  </div>
  <ChatBubble
    v-else-if="settingsStore.chatMode === 'chat'"
    v-bind="props"
    :show-actions="showActions"
  />
  <ToolBubble v-else v-bind="props" />
</template>

<style scoped>
.child-agent-event-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  width: 100%;
}

.child-agent-event-avatar-slot {
  width: 36px;
  flex: 0 0 36px;
}

.child-agent-event-row :deep(.child-agent-event) {
  flex: 1;
  min-width: 0;
  margin-left: 0;
}

.system-wakeup-strip {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  max-width: min(100%, 520px);
  gap: var(--space-6);
  margin: var(--space-6) 0;
  padding: var(--space-4) var(--space-10);
  border: 1px dashed var(--color-border-strong);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.system-wakeup-icon {
  flex: 0 0 auto;
  color: var(--color-primary);
}
</style>
