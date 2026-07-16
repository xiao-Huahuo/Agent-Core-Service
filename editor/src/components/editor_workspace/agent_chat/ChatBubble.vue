<!--
  Chat mode message bubble.

  Usage:
  Ported from console ChatBubble. Assistant thinking is deduplicated and can
  collapse once final content starts streaming.
  Shows retrieved knowledge sources below assistant content.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import KnowledgeSources from '@/components/editor_workspace/agent_chat/KnowledgeSources.vue'
import MarkdownContent from '@/components/editor_workspace/agent_chat/MarkdownContent.vue'
import ThinkingInline from '@/components/editor_workspace/agent_chat/ThinkingInline.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { AgentChatMessage, SourceItem } from '@/stores/chat'

const props = defineProps<{
  message: AgentChatMessage
  isStreaming?: boolean
  userAvatar: string
  agentAvatar: string
  showAvatar?: boolean
  knowledgeSources?: SourceItem[]
  citationMap?: Record<string, SourceItem>
}>()

const workspaceStore = useWorkspaceStore()

const bubbleRadius = computed(() => {
  return props.message.role === 'user' ? '18px 4px 18px 18px' : '4px 18px 18px 18px'
})

const thinkingRevealed = ref(true)
const thinkingAutoCollapsed = ref(false)

watch(
  () => props.isStreaming,
  (streaming) => {
    if (!streaming) {
      thinkingRevealed.value = false
    }
  },
)

watch(
  () => props.message.content,
  (content) => {
    if (thinkingAutoCollapsed.value) {
      return
    }
    if (props.isStreaming && thinkingRevealed.value && content && content !== '​') {
      thinkingRevealed.value = false
      thinkingAutoCollapsed.value = true
    }
  },
)

watch(
  () => props.message.message_id,
  () => {
    thinkingAutoCollapsed.value = false
    thinkingRevealed.value = true
  },
)

const thinkingTraces = computed(() => {
  const seen = new Set<string>()
  return (props.message.trace ?? []).filter((trace) => {
    const humanReadable = typeof trace.human_readable === 'string' ? trace.human_readable : ''
    const isChatVisible = trace.chat_visible === true || trace.event === 'tool_call_end'
    if (!humanReadable || seen.has(humanReadable)) {
      return false
    }
    if (!isChatVisible) {
      return false
    }
    seen.add(humanReadable)
    return true
  })
})

const hasAssistantContent = computed(() => {
  return Boolean(props.message.content && props.message.content !== '​')
})

const shouldRenderAssistant = computed(() => {
  return props.message.role === 'assistant'
    && (hasAssistantContent.value || thinkingTraces.value.length > 0 || props.isStreaming)
})

const shouldRenderAssistantBubble = computed(() => {
  return hasAssistantContent.value || (props.isStreaming && thinkingTraces.value.length === 0)
})

function handleNavigateSource(uri: string) {
  if (/^https?:\/\//i.test(uri)) {
    if (window.agentEditorDesktop?.openExternal) {
      void window.agentEditorDesktop.openExternal(uri)
    } else {
      window.open(uri, '_blank', 'noopener,noreferrer')
    }
    return
  }
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
  <div v-if="shouldRenderAssistant" class="bubble-row assistant">
    <img :src="agentAvatar" class="avatar" alt="agent" />
    <div class="bubble-col">
      <span v-if="message.node && message.node !== 'assistant'" class="node-label">{{ message.node }}</span>
      <Transition name="think-slide">
        <div v-if="thinkingTraces.length > 0 && (isStreaming || thinkingRevealed)" class="thinking-wrapper">
          <ThinkingInline
            :traces="thinkingTraces"
            :is-streaming="isStreaming"
            :default-expanded="thinkingRevealed"
            @collapse="thinkingRevealed = false"
          />
          <button
            v-if="!isStreaming && thinkingRevealed"
            class="thinking-toggle thinking-close"
            type="button"
            @click="thinkingRevealed = false"
          >
            收起
          </button>
        </div>
      </Transition>
      <Transition name="think-fade">
        <button
          v-if="thinkingTraces.length > 0 && !isStreaming && !thinkingRevealed"
          class="thinking-toggle"
          type="button"
          @click="thinkingRevealed = true"
        >
          思考过程
        </button>
      </Transition>
      <div v-if="shouldRenderAssistantBubble" class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent
          v-if="hasAssistantContent"
          :content="message.content"
          :is-streaming="isStreaming"
          :citation-map="citationMap"
          :on-navigate-source="handleNavigateSource"
        />
        <span v-if="isStreaming && !hasAssistantContent" class="cursor">|</span>
      </div>
      <KnowledgeSources
        v-if="knowledgeSources && knowledgeSources.length > 0"
        :sources="knowledgeSources"
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

.avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  margin-top: 2px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  object-fit: cover;
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

.node-label {
  margin-bottom: var(--space-4);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.thinking-wrapper {
  margin-bottom: var(--space-8);
  overflow: hidden;
}

.think-slide-enter-active {
  overflow: hidden;
  transition:
    max-height 0.35s ease,
    opacity 0.25s ease,
    margin-bottom 0.35s ease;
}

.think-slide-leave-active {
  overflow: hidden;
  transition:
    max-height 0.25s ease,
    opacity 0.2s ease,
    margin-bottom 0.25s ease;
}

.think-slide-enter-from {
  max-height: 0;
  margin-bottom: 0;
  opacity: 0;
}

.think-slide-enter-to {
  max-height: 800px;
  margin-bottom: var(--space-8);
  opacity: 1;
}

.think-slide-leave-from {
  max-height: 800px;
  margin-bottom: var(--space-8);
  opacity: 1;
}

.think-slide-leave-to {
  max-height: 0;
  margin-bottom: 0;
  opacity: 0;
}

.think-fade-enter-active {
  transition: opacity 0.25s ease;
}

.think-fade-leave-active {
  transition: opacity 0.15s ease;
}

.think-fade-enter-from,
.think-fade-leave-to {
  opacity: 0;
}

.thinking-toggle {
  display: inline-block;
  padding: 0 0 var(--space-6);
  border: 0;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 9px;
  opacity: 0.45;
  transition:
    opacity var(--transition-fast),
    color var(--transition-fast);
}

.thinking-toggle:hover {
  color: var(--color-accent);
  opacity: 0.8;
}

.thinking-close {
  padding: var(--space-6) 0 0;
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
