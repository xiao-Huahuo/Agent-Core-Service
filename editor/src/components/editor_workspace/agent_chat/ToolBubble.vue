<!--
  Tool mode message bubble.

  Usage:
  Matches console ToolBubble: action node traces render as full-width tool call
  rows, while other assistant nodes render only their content without node labels.
  Shows retrieved knowledge sources below assistant content.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-vue-next'

import AttachmentBlocks from '@/components/editor_workspace/agent_chat/AttachmentBlocks.vue'
import KnowledgeSources from '@/components/editor_workspace/agent_chat/KnowledgeSources.vue'
import MarkdownContent from '@/components/editor_workspace/agent_chat/MarkdownContent.vue'
import ToolCallInline from '@/components/editor_workspace/agent_chat/ToolCallInline.vue'
import { useChatStore } from '@/stores/chat'
import { useWorkspaceStore } from '@/stores/workspace'
import type { AgentChatMessage, AgentUploadedAttachment, SourceItem } from '@/stores/chat'

const props = defineProps<{
  message: AgentChatMessage
  isStreaming?: boolean
  userAvatar: string
  agentAvatar: string
  showAvatar?: boolean
  showActions?: boolean
  knowledgeSources?: SourceItem[]
  citationMap?: Record<string, SourceItem>
}>()

const workspaceStore = useWorkspaceStore()
const chatStore = useChatStore()
const copied = ref(false)
const feedback = ref<'up' | 'down' | null>(null)
const feedbackBurst = ref<'up' | 'down' | null>(null)

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

const copyableContent = computed(() => {
  return props.message.content?.trim() || ''
})

function fallbackCopy(text: string) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

async function copyBubbleContent() {
  const text = copyableContent.value
  if (!text) {
    return
  }
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
  } else {
    fallbackCopy(text)
  }
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1200)
}

function setFeedback(kind: 'up' | 'down') {
  feedback.value = kind
  feedbackBurst.value = null
  window.requestAnimationFrame(() => {
    feedbackBurst.value = kind
    window.setTimeout(() => {
      feedbackBurst.value = null
    }, 420)
  })
}

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

function removeAttachment(attachment: AgentUploadedAttachment) {
  void chatStore.deleteAttachment(attachment)
}
</script>

<template>
  <div v-if="message.role === 'assistant' && message.node === 'action' && hasToolTrace" class="action-row">
    <ToolCallInline :traces="message.trace ?? []" />
  </div>

  <div v-else-if="shouldRenderAssistant" class="bubble-row assistant tool-assistant-row">
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
      <div v-if="hasContent || (isStreaming && statusTraces.length === 0)" class="assistant-article">
        <MarkdownContent
          v-if="hasContent"
          :content="message.content"
          :is-streaming="isStreaming"
          :citation-map="citationMap"
          :on-navigate-source="handleNavigateSource"
        />
        <span v-if="isStreaming && !hasContent" class="cursor">|</span>
      </div>
      <div v-if="showActions !== false && copyableContent" class="message-actions">
        <button
          class="copy-action"
          type="button"
          :title="copied ? 'Copied' : 'Copy'"
          :aria-label="copied ? 'Copied' : 'Copy message'"
          @click="copyBubbleContent"
        >
          <Check v-if="copied" :size="12" />
          <Copy v-else :size="12" />
        </button>
        <button
          class="feedback-action feedback-up"
          :class="{ active: feedback === 'up', burst: feedbackBurst === 'up' }"
          type="button"
          title="Like"
          aria-label="Like response"
          @click="setFeedback('up')"
        >
          <ThumbsUp :size="12" />
        </button>
        <button
          class="feedback-action feedback-down"
          :class="{ active: feedback === 'down', burst: feedbackBurst === 'down' }"
          type="button"
          title="Dislike"
          aria-label="Dislike response"
          @click="setFeedback('down')"
        >
          <ThumbsDown :size="12" />
        </button>
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
      <AttachmentBlocks
        v-if="message.attachments?.length"
        class="message-attachments"
        :attachments="message.attachments"
        align="right"
        @remove="removeAttachment"
      />
      <div v-if="message.reference" class="reference-block">
        <span class="reference-content">{{ message.reference }}</span>
      </div>
      <div class="bubble user" :style="{ borderRadius: bubbleRadius }">
        <pre class="content">{{ message.content }}</pre>
      </div>
      <button
        v-if="copyableContent"
        class="copy-action"
        type="button"
        :title="copied ? 'Copied' : 'Copy'"
        :aria-label="copied ? 'Copied' : 'Copy message'"
        @click="copyBubbleContent"
      >
        <Check v-if="copied" :size="12" />
        <Copy v-else :size="12" />
      </button>
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
  width: 100%;
  max-width: none;
}

.tool-assistant-row {
  align-self: stretch;
  width: 100%;
  max-width: none;
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

.action-row {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: none;
  margin-bottom: var(--space-12);
}

.bubble-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.bubble-row.assistant .bubble-col {
  align-items: stretch;
  width: 100%;
}

.bubble-row.user .bubble-col {
  align-items: flex-end;
}

.message-attachments {
  max-width: min(100%, 360px);
  margin-bottom: var(--space-6);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.assistant-article {
  width: 100%;
  max-width: none;
  color: var(--color-text-primary);
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

.copy-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-top: var(--space-4);
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  opacity: 0.56;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    opacity var(--transition-fast);
}

.copy-action:hover {
  background: rgba(148, 163, 184, 0.12);
  color: var(--color-text-secondary);
  opacity: 1;
}

.message-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.message-actions .copy-action {
  margin-top: 0;
}

.bubble-row.assistant .message-actions {
  align-self: flex-start;
}

.feedback-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  opacity: 0.56;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    opacity var(--transition-fast),
    transform 120ms ease;
}

.feedback-action:hover {
  background: rgba(148, 163, 184, 0.12);
  opacity: 1;
}

.feedback-action.feedback-up:hover,
.feedback-action.feedback-up.active {
  color: #ef4b72;
}

.feedback-action.feedback-down:hover,
.feedback-action.feedback-down.active {
  color: #7f92b2;
}

.feedback-action.burst {
  animation: feedback-pop 420ms cubic-bezier(0.2, 1.55, 0.35, 1);
}

@keyframes feedback-pop {
  0% { transform: scale(1); }
  42% { transform: scale(1.34) rotate(-8deg); }
  68% { transform: scale(0.88) rotate(4deg); }
  100% { transform: scale(1) rotate(0); }
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
