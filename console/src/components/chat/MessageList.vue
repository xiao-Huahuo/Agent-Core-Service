<!--
  消息列表组件。
  作用:
  1. 渲染当前会话的消息气泡列表。
  2. 在用户原本停留在底部时，流式输出自动跟随到底部。
  3. 当用户主动向上滚动查看历史消息时，不再强制抢回滚动位置。
-->

<script setup>
import { computed, watch, ref, nextTick, onMounted } from 'vue'
import { useAvatar } from '@/composable/useAvatar'
import MessageBubble from './MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  isStreaming: { type: Boolean, default: false },
  mergeAssistants: { type: Boolean, default: false },
})

const { userAvatar, agentAvatar } = useAvatar()

/** 合并连续 assistant 消息的辅助函数 */
function mergeConsecutiveAssistants(msgs) {
  return msgs.filter(m => m.role !== 'system').reduce((acc, msg) => {
    if (msg.role === 'assistant' && acc.length > 0 && acc[acc.length - 1].role === 'assistant') {
      const prev = acc[acc.length - 1]
      acc[acc.length - 1] = {
        ...prev,
        content: msg.content || prev.content,
        node: msg.node || prev.node,
        tool_calls: msg.tool_calls?.length ? msg.tool_calls : prev.tool_calls,
        trace: [...(prev.trace || []), ...(msg.trace || [])],
      }
    } else {
      acc.push(msg)
    }
    return acc
  }, [])
}

const visibleMessages = computed(() => {
  const base = props.messages.filter(m => m.role !== 'system')
  return props.mergeAssistants ? mergeConsecutiveAssistants(base) : base
})

const containerRef = ref(null)
const isPinnedToBottom = ref(true)

/** 是否需要在模板中渲染"思考中"占位气泡:
 *  流式已开始(isStreaming) 且 消息列表末尾不是 assistant 消息。 */
const showThinkingBubble = computed(() => {
  if (!props.isStreaming) return false
  const list = visibleMessages.value
  if (list.length === 0) return true
  return list[list.length - 1].role !== 'assistant'
})

/**
 * 判断当前滚动位置是否仍然贴近底部。
 * 使用一个小阈值，避免因为子像素误差导致"明明在底部却判定不在底部"。
 */
function isNearBottom() {
  const container = containerRef.value
  if (!container) return true

  const threshold = 24
  const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight
  return distanceToBottom <= threshold
}

/**
 * 将消息列表滚动到底部。
 */
function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
}

/**
 * 在用户主动滚动时更新"是否跟随到底部"的状态。
 * 如果用户已经上滚查看历史消息，则后续流式推送不再强制把视图拖回底部。
 */
function handleScroll() {
  isPinnedToBottom.value = isNearBottom()
}

/**
 * 仅在用户原本就在底部时才自动滚动。
 * 这里在 DOM 更新前先读取当前滚动位置，避免内容变长后误判为"不在底部"。
 */
function scheduleScrollIfNeeded() {
  const shouldAutoScroll = isPinnedToBottom.value || isNearBottom()
  nextTick(() => {
    if (shouldAutoScroll) {
      scrollToBottom()
      isPinnedToBottom.value = true
    }
  })
}

watch(() => props.messages.length, scheduleScrollIfNeeded)
watch(
  () => {
    const msgs = props.messages
    return msgs.length > 0 ? msgs[msgs.length - 1].content : ''
  },
  scheduleScrollIfNeeded
)

onMounted(() => {
  scrollToBottom()
  isPinnedToBottom.value = true
})
</script>

<template>
  <div ref="containerRef" class="message-list" @scroll="handleScroll">
    <p v-if="visibleMessages.length === 0" class="empty-hint">
      $ 输入消息开始对话
    </p>

    <MessageBubble
      v-for="(msg, idx) in visibleMessages"
      :key="idx"
      :message="msg"
      :is-streaming="isStreaming && idx === visibleMessages.length - 1"
      :user-avatar="userAvatar"
      :agent-avatar="agentAvatar"
      :show-avatar="msg.role !== 'assistant' || idx === 0 || visibleMessages[idx - 1].role !== 'assistant'"
    />

    <!-- 思考中占位: 头像 + 悬空文字 -->
    <div v-if="showThinkingBubble" class="thinking-row">
      <img :src="agentAvatar" class="thinking-avatar" alt="agent" />
      <span class="thinking-text">思考中<span class="dot-anim">...</span></span>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: var(--space-16);
  scrollbar-width: none;
}

.message-list::-webkit-scrollbar {
  display: none;
}

.empty-hint {
  text-align: center;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  margin-top: var(--space-32);
}

/* ---- 思考中悬空文字 ---- */
.thinking-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-8) 0;
  align-self: flex-start;
}

.thinking-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--color-border);
}

.thinking-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  opacity: 0.55;
}

.dot-anim {
  animation: dot-blink 1.2s step-end infinite;
}

@keyframes dot-blink {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
</style>
