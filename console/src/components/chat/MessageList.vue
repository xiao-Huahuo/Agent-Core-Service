<!--
  消息列表 — 自动滚底, 传递头像给气泡。
-->

<script setup>
import { watch, ref, nextTick } from 'vue'
import { useAvatar } from '@/composable/useAvatar'
import MessageBubble from './MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  isStreaming: { type: Boolean, default: false },
})

const { userAvatar, agentAvatar } = useAvatar()

const containerRef = ref(null)

function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
}

watch(() => props.messages.length, () => nextTick(scrollToBottom))
watch(
  () => {
    const msgs = props.messages
    return msgs.length > 0 ? msgs[msgs.length - 1].content : ''
  },
  () => nextTick(scrollToBottom)
)
</script>

<template>
  <div ref="containerRef" class="message-list">
    <p v-if="messages.length === 0" class="empty-hint">
      $ 输入消息开始对话
    </p>

    <MessageBubble
      v-for="(msg, idx) in messages"
      :key="idx"
      :message="msg"
      :is-streaming="isStreaming && idx === messages.length - 1"
      :user-avatar="userAvatar"
      :agent-avatar="agentAvatar"
    />
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: var(--space-16);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  margin-top: var(--space-32);
}
</style>
