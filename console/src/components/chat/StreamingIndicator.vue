<!--
  流式思考指示器 — 脉冲圆点 + 节点名称。
-->

<script setup>
import { useChatStore } from '@/stores/chat'

defineProps({
  isStreaming: { type: Boolean, default: false },
  hasContent: { type: Boolean, default: false },
})

const chatStore = useChatStore()
</script>

<template>
  <div v-if="isStreaming && !hasContent" class="streaming-indicator">
    <span class="dot"></span>
    <span class="dot"></span>
    <span class="dot"></span>
    <span v-if="chatStore.currentNode" class="node-name">{{ chatStore.currentNode }}</span>
  </div>
</template>

<style scoped>
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: var(--space-8) var(--space-16);
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 1.2s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

.node-name {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-tertiary);
  margin-left: 6px;
  text-transform: uppercase;
}

@keyframes pulse {
  0%, 60%, 100% { opacity: 0.15; }
  30% { opacity: 1; }
}
</style>
