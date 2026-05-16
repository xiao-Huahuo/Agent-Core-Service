<!--
  消息气泡 — iMessage 风格 + 头像。
  直角始终在顶部 (agent 左上角, user 右上角), 头像对齐气泡顶部。
-->

<script setup>
import { computed, ref, watch } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
import ThinkingInline from './ThinkingInline.vue'

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

const thinkingRevealed = ref(true)

watch(
  () => props.isStreaming,
  (streaming) => {
    if (!streaming) thinkingRevealed.value = false
  }
)

/** 过滤出有 human_readable 的思考步骤,去重(按 human_readable 文本) */
const thinkingTraces = computed(() => {
  const traces = props.message.trace || []
  const seen = new Set()
  return traces.filter(t => {
    if (!t.human_readable) return false
    if (seen.has(t.human_readable)) return false
    seen.add(t.human_readable)
    return true
  })
})
</script>

<template>
  <!-- Agent 消息: 头像在左 -->
  <div v-if="message.role === 'assistant'" class="bubble-row assistant">
    <img :src="agentAvatar" class="avatar" alt="agent" />
    <div class="bubble-col">
      <span v-if="message.node" class="node-label">{{ message.node }}</span>
      <Transition name="think-slide">
        <div v-if="thinkingTraces.length > 0 && (isStreaming || thinkingRevealed)" class="thinking-wrapper">
          <ThinkingInline :traces="thinkingTraces" :is-streaming="isStreaming" :default-expanded="thinkingRevealed" @collapse="thinkingRevealed = false" />
          <button
            v-if="!isStreaming && thinkingRevealed"
            class="thinking-toggle thinking-close"
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
          @click="thinkingRevealed = true"
        >
          思考过程
        </button>
      </Transition>
      <div v-if="message.content || isStreaming" class="bubble assistant" :style="{ borderRadius: bubbleRadius }">
        <MarkdownContent v-if="message.content" :content="message.content" :is-streaming="isStreaming" />
        <span v-if="isStreaming" class="cursor">|</span>
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

  <!-- 系统消息: 居中灰显 -->
  <div v-else-if="message.role === 'system'" class="bubble-row system">
    <div class="bubble system-bubble">
      <span class="system-role">{{ message.role }}</span>
      <pre class="content system-content">{{ message.content }}</pre>
    </div>
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

/* ---- 思考过程外框 ---- */
.thinking-wrapper {
  margin-bottom: var(--space-8);
  overflow: hidden;
}

/* 展开: 向下滑入 */
.think-slide-enter-active {
  transition: max-height 0.35s ease, opacity 0.25s ease, margin-bottom 0.35s ease;
  overflow: hidden;
}

.think-slide-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease, margin-bottom 0.25s ease;
  overflow: hidden;
}

.think-slide-enter-from {
  max-height: 0;
  opacity: 0;
  margin-bottom: 0;
}

.think-slide-enter-to {
  max-height: 800px;
  opacity: 1;
  margin-bottom: var(--space-8);
}

.think-slide-leave-from {
  max-height: 800px;
  opacity: 1;
  margin-bottom: var(--space-8);
}

.think-slide-leave-to {
  max-height: 0;
  opacity: 0;
  margin-bottom: 0;
}

/* 链接: 淡入淡出 */
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
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: none;
  padding: 0 0 var(--space-6) 0;
  cursor: pointer;
  opacity: 0.45;
  transition: opacity var(--transition-fast), color var(--transition-fast);
}

.thinking-toggle:hover {
  opacity: 0.8;
  color: var(--color-accent);
}

.thinking-close {
  padding: var(--space-6) 0 0 0;
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
