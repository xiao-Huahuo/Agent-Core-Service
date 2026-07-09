<!--
  Tool mode message bubble.

  Usage:
  Matches console ToolBubble: action node traces render as full-width tool call
  rows, while other assistant nodes render only their content without node labels.
-->
<script setup lang="ts">
import { computed } from 'vue'

import MarkdownContent from '@/components/editor_workspace/agent_chat/MarkdownContent.vue'
import ToolCallInline from '@/components/editor_workspace/agent_chat/ToolCallInline.vue'
import type { AgentChatMessage } from '@/stores/chat'

const props = defineProps<{
  message: AgentChatMessage
  isStreaming?: boolean
  userAvatar: string
  agentAvatar: string
  showAvatar?: boolean
}>()

const hasContent = computed(() => {
  const content = props.message.content
  return content && content !== '\u200b'
})

const bubbleRadius = computed(() => {
  return props.message.role === 'user' ? '18px 4px 18px 18px' : '4px 18px 18px 18px'
})
</script>

<template>
  <div v-if="message.role === 'assistant' && message.node === 'action'" class="action-row">
    <ToolCallInline :traces="message.trace ?? []" />
  </div>

  <div v-else-if="message.role === 'assistant'" class="bubble-row assistant">
    <img v-if="showAvatar" :src="agentAvatar" class="avatar" alt="agent" />
    <div v-else class="avatar-spacer"></div>
    <div class="bubble-col">
      <div v-if="hasContent || isStreaming" class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent v-if="hasContent" :content="message.content" :is-streaming="isStreaming" />
        <span v-if="isStreaming" class="cursor">|</span>
      </div>
    </div>
  </div>

  <div v-else-if="message.role === 'user'" class="bubble-row user">
    <div class="bubble-col">
      <div v-if="message.reference" class="reference-block">
        <span class="reference-content">{{ message.reference }}</span>
      </div>
      <div class="bubble user" :style="{ borderRadius: bubbleRadius }">
        <pre class="content">{{ message.content }}</pre>
      </div>
    </div>
    <img :src="userAvatar" class="avatar" alt="user" />
  </div>

  <div v-else class="bubble-row system">
    <div class="bubble system-bubble">
      <span class="system-role">{{ message.role }}</span>
      <pre class="content system-content">{{ message.content }}</pre>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  max-width: min(84%, 500px);
  margin-bottom: var(--space-12);
}

.bubble-row.user {
  align-self: flex-end;
}

.bubble-row.assistant {
  align-self: flex-start;
}

.avatar,
.avatar-spacer {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar {
  border: 1px solid var(--color-border);
  border-radius: 50%;
  object-fit: cover;
}

.action-row {
  width: 100%;
  margin-bottom: var(--space-12);
}

.bubble-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.bubble-row.assistant .bubble-col {
  align-items: flex-start;
}

.bubble-row.user .bubble-col {
  align-items: flex-end;
}

.reference-block {
  max-width: 100%;
  margin-bottom: var(--space-4);
  padding: 7px 10px;
  border-left: 2px solid var(--color-border);
  background: rgba(148, 163, 184, 0.08);
  color: var(--color-text-muted);
  font-family: var(--font-chat);
  font-size: 12px;
  line-height: 1.4;
}

.reference-content {
  display: -webkit-box;
  overflow: hidden;
  text-overflow: ellipsis;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  white-space: pre-wrap;
}

.bubble {
  display: inline-block;
  max-width: 100%;
  padding: 10px 16px;
  border: 1px solid;
  word-break: break-word;
  backdrop-filter: blur(var(--blur-strength));
}

.bubble.user {
  border-color: var(--color-user-bubble-border);
  background: var(--color-user-bubble);
  box-shadow:
    inset 0 1px 0 var(--color-user-bubble-highlight),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    0 0 18px var(--color-user-bubble-glow);
}

.bubble.assistant {
  border-color: var(--color-agent-bubble-border);
  background: var(--color-agent-bubble);
  box-shadow:
    inset 0 1px 0 var(--color-agent-bubble-highlight),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    0 0 18px var(--color-agent-bubble-glow);
}

.content {
  margin: 0;
  color: var(--color-text-primary);
  font-family: var(--font-chat);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
}

.bubble-row.system {
  align-self: center;
  max-width: 90%;
  margin-bottom: var(--space-8);
}

.system-bubble {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 6px 12px;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.02);
}

.system-role {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.system-content {
  max-height: 120px;
  overflow-y: auto;
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.cursor {
  color: var(--color-accent);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
