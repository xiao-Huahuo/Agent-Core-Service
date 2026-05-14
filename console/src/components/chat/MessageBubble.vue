<!--
  消息气泡 — iMessage 风格 + 头像。
  直角始终在顶部 (agent 左上角, user 右上角), 头像对齐气泡顶部。
-->

<script setup>
import { computed } from 'vue'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false },
  userAvatar: { type: String, default: '' },
  agentAvatar: { type: String, default: '' },
})

/** agent: 左上直角指向左头像, user: 右上直角指向右头像 */
const bubbleRadius = computed(() => {
  return props.message.role === 'user'
    ? '18px 4px 18px 18px'
    : '4px 18px 18px 18px'
})
</script>

<template>
  <!-- Agent 消息: 头像在左 -->
  <div v-if="message.role === 'assistant'" class="bubble-row assistant">
    <img :src="agentAvatar" class="avatar" alt="agent" />
    <div class="bubble-col">
      <span v-if="message.node" class="node-label">{{ message.node }}</span>
      <div class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent v-if="message.content" :content="message.content" :is-streaming="isStreaming" />
        <span v-if="isStreaming" class="cursor">|</span>
      </div>
    </div>
  </div>

  <!-- User 消息: 头像在右 -->
  <div v-else class="bubble-row user">
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

/* ---- 列 ---- */
.bubble-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.bubble-col:last-child {
  align-items: flex-end;
}

/* agent 的 col 在头像右边,左对齐 */
.bubble-row.assistant .bubble-col {
  align-items: flex-start;
}
.bubble-row.user .bubble-col {
  align-items: flex-end;
}

/* ---- 节点标签 ---- */
.node-label {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ---- 气泡 ---- */
.bubble {
  display: inline-block;
  padding: 10px 16px;
  max-width: 100%;
  border: 1px solid;
  word-break: break-word;
}

.bubble.user {
  background: var(--color-user-bubble);
  border-color: var(--color-user-bubble-border);
}

.bubble.assistant {
  background: rgba(255,255,255,0.025);
  border-color: var(--color-border);
}

.content {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--color-text-primary);
  white-space: pre-wrap;
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
