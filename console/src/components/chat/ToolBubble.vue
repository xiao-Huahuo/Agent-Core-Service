<!--
  ToolBubble —— 工具模式消息气泡。
  思考步骤内联展示（planner → 工具调用 → observation → 最终回答），无折叠面板。
-->

<script setup>
import { computed } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
import ToolCallInline from './ToolCallInline.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false },
  userAvatar: { type: String, default: '' },
  agentAvatar: { type: String, default: '' },
  showAvatar: { type: Boolean, default: true },
})

const hasContent = computed(() => {
  const c = props.message.content
  return c && c !== '​'
})

const statusTraces = computed(() => {
  const seen = new Set()
  return (props.message.trace || []).filter((trace) => {
    const isChatVisible = trace.chat_visible === true
    if (!trace.human_readable || trace.event === 'tool_call_start' || trace.event === 'tool_call_end') return false
    if (!isChatVisible) return false
    if (seen.has(trace.human_readable)) return false
    seen.add(trace.human_readable)
    return true
  })
})

const hasToolTrace = computed(() => {
  return (props.message.trace || []).some(trace => trace.tool_name && (trace.event === 'tool_call_start' || trace.event === 'tool_call_end'))
})

const shouldRenderAssistant = computed(() => {
  return props.message.role === 'assistant'
    && (hasContent.value || statusTraces.value.length > 0 || props.isStreaming)
})

const bubbleRadius = computed(() => {
  return props.message.role === 'user'
    ? '18px 4px 18px 18px'
    : '4px 18px 18px 18px'
})


</script>

<template>
  <!-- action 节点: 整行宽度的工具条 -->
  <div v-if="message.role === 'assistant' && message.node === 'action' && hasToolTrace" class="action-row">
    <ToolCallInline :traces="message.trace || []" />
  </div>

  <!-- Agent 消息: 只在连续组首条显示头像 -->
  <div v-else-if="shouldRenderAssistant" class="bubble-row assistant">
    <img v-if="showAvatar" :src="agentAvatar" class="avatar" alt="agent" />
    <div v-else class="avatar-spacer" />
    <div class="bubble-col">
      <div v-if="statusTraces.length > 0 && !hasContent" class="status-lines">
        <p v-for="trace in statusTraces" :key="`${trace.node}-${trace.event}-${trace.human_readable}`" class="status-line">
          {{ trace.human_readable }}
        </p>
      </div>
      <div v-if="hasContent || (isStreaming && statusTraces.length === 0)" class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent v-if="hasContent" :content="message.content" :is-streaming="isStreaming" />
        <span v-if="isStreaming && !hasContent" class="cursor">|</span>
      </div>
    </div>
  </div>

  <!-- User 消息: 头像在右 -->
  <div v-else-if="message.role === 'user'" class="bubble-row user">
    <div class="bubble-col">
      <div class="bubble user" :style="{ borderRadius: bubbleRadius }">
        <pre class="content">{{ message.content }}</pre>
      </div>
    </div>
    <img :src="userAvatar" class="avatar" alt="user" />
  </div>

</template>

<style scoped>
/* ---- 行 ---- */
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  margin-bottom: var(--space-12);
  max-width: 84%;
}

.bubble-row.user {
  align-self: flex-end;
}

.bubble-row.assistant {
  align-self: flex-start;
}

/* ---- 头像 ---- */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  margin-top: 2px;
  border: 1px solid var(--color-border);
}

.avatar-spacer {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  margin-top: 2px;
}

/* ---- action 整行宽度的工具条 ---- */
.action-row {
  width: 100%;
  margin-bottom: var(--space-12);
}

/* ---- 列 ---- */
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

/* ---- 气泡 ---- */
.bubble {
  display: inline-block;
  padding: 10px 16px;
  max-width: 100%;
  border: 1px solid;
  word-break: break-word;
  backdrop-filter: blur(var(--blur-strength));
  -webkit-backdrop-filter: blur(var(--blur-strength));
}

.bubble.user {
  background: var(--color-user-bubble);
  border-color: var(--color-user-bubble-border);
  box-shadow:
    inset 0 1px 0 var(--color-user-bubble-highlight),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    0 0 18px var(--color-user-bubble-glow);
}

.bubble.assistant {
  background: var(--color-agent-bubble);
  border-color: var(--color-agent-bubble-border);
  box-shadow:
    inset 0 1px 0 var(--color-agent-bubble-highlight),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    0 0 18px var(--color-agent-bubble-glow);
}

.content {
  margin: 0;
  font-family: var(--font-chat);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--color-text-primary);
  white-space: pre-wrap;
}

/* ---- 系统 / 工具消息 ---- */
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
  background: rgba(255,255,255,0.02);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
}

.system-role {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.system-content {
  font-size: 11px;
  color: var(--color-text-tertiary);
  max-height: 120px;
  overflow-y: auto;
}

/* ---- 流式光标 ---- */
.cursor {
  color: var(--color-accent);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
