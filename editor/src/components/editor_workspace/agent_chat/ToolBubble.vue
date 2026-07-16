<!--
  Tool mode message bubble.

  Usage:
  Matches console ToolBubble: action node traces render as full-width tool call
  rows, while other assistant nodes render only their content without node labels.
  Shows retrieved knowledge sources below assistant content.
-->
<script setup lang="ts">
import { computed } from 'vue'

import KnowledgeSources from '@/components/editor_workspace/agent_chat/KnowledgeSources.vue'
import MarkdownContent from '@/components/editor_workspace/agent_chat/MarkdownContent.vue'
import ToolCallInline from '@/components/editor_workspace/agent_chat/ToolCallInline.vue'
import { useWorkspaceStore } from '@/stores/workspace'
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

const workspaceStore = useWorkspaceStore()

const hasContent = computed(() => {
  const content = props.message.content
  return content && content !== '​'
})

const statusTraces = computed(() => {
  const seen = new Set<string>()
  return (props.message.trace ?? []).filter((trace) => {
    const humanReadable = typeof trace.human_readable === 'string' ? trace.human_readable : ''
    const isChatVisible = trace.chat_visible === true
    if (!humanReadable || trace.event === 'tool_call_start' || trace.event === 'tool_call_end') return false
    if (!isChatVisible) return false
    if (seen.has(humanReadable)) return false
    seen.add(humanReadable)
    return true
  })
})

const hasToolTrace = computed(() => {
  return (props.message.trace ?? []).some((trace) => {
    return trace.tool_name && (trace.event === 'tool_call_start' || trace.event === 'tool_call_end')
  })
})

const shouldRenderAssistant = computed(() => {
  return props.message.role === 'assistant'
    && (hasContent.value || statusTraces.value.length > 0 || props.isStreaming)
})

const bubbleRadius = computed(() => {
  return props.message.role === 'user' ? '18px 4px 18px 18px' : '4px 18px 18px 18px'
})

function handleNavigateSource(uri: string) {
  const flatNodes = workspaceStore.flatNodes ?? []
  const normalizePath = (value: string) => value.replace(/\\/g, '/').replace(/^\/+/, '')
  const normalizedUri = normalizePath(uri)
  let node = flatNodes.find((n) => normalizePath(n.path) === normalizedUri)
  if (!node) {
    const parts = normalizedUri.split('/').filter(Boolean)
    const name = parts[parts.length - 1] ?? uri
    node = flatNodes.find((n) => {
      const normalizedPath = normalizePath(n.path)
      return normalizedPath.endsWith(`/${normalizedUri}`)
        || normalizedPath.endsWith(`/${name}`)
        || n.name === name
    })
  }
  if (node) {
    workspaceStore.setMainView('editor')
    workspaceStore.selectFile(node)
  }
}
</script>

<template>
  <div v-if="message.role === 'assistant' && message.node === 'action' && hasToolTrace" class="action-row">
    <ToolCallInline :traces="message.trace ?? []" />
  </div>

  <div v-else-if="shouldRenderAssistant" class="bubble-row assistant">
    <img v-if="showAvatar" :src="agentAvatar" class="avatar" alt="agent" />
    <div v-else class="avatar-spacer"></div>
    <div class="bubble-col">
      <div v-if="statusTraces.length > 0 && !hasContent" class="status-lines">
        <p
          v-for="trace in statusTraces"
          :key="`${trace.node}-${trace.event}-${trace.human_readable}`"
          class="status-line"
        >
          {{ trace.human_readable }}
        </p>
      </div>
      <div v-if="hasContent || (isStreaming && statusTraces.length === 0)" class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent
          v-if="hasContent"
          :content="message.content"
          :is-streaming="isStreaming"
          :citation-map="citationMap"
          :on-navigate-source="handleNavigateSource"
        />
        <span v-if="isStreaming && !hasContent" class="cursor">|</span>
      </div>
      <KnowledgeSources
        v-if="!isStreaming && knowledgeSources && knowledgeSources.length > 0"
        :sources="knowledgeSources"
        :citation-map="citationMap ?? {}"
      />
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

.status-lines {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}

.status-line {
  margin: 0;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: var(--line-height-normal);
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
