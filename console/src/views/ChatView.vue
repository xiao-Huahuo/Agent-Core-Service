<!--
  聊天页面 — 消息列表 + 输入框。
  侧边栏已移至 App.vue,本组件仅负责聊天主区域。
-->

<script setup>
import { ref } from 'vue'
import { useUserId } from '@/composable/useUserId'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import MessageList from '@/components/chat/MessageList.vue'
import StreamingIndicator from '@/components/chat/StreamingIndicator.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const { userId, hasUserId, setUserId } = useUserId()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const userIdInput = ref(userId.value)

async function submitUserId() {
  const id = userIdInput.value.trim()
  if (!id) return
  setUserId(id)
  await sessionStore.load(id)
}

async function handleSend(text) {
  if (chatStore.isStreaming) return
  let sessionId = sessionStore.currentSessionId
  if (!sessionId) {
    sessionId = await sessionStore.create(userId.value)
    sessionStore.select(sessionId)
    /* 新会话历史为空，直接发送 */
  }
  await chatStore.send(userId.value, sessionId, text)
}
</script>

<template>
  <div class="chat-view">
    <!-- ================================================================
         user_id 设置界面
         ================================================================ -->
    <div v-if="!hasUserId" class="user-id-prompt">
      <div class="macos-card prompt-card">
        <div class="macos-card-titlebar">
          <div class="traffic-lights">
            <span class="traffic-dot sm red"></span>
            <span class="traffic-dot sm yellow"></span>
            <span class="traffic-dot sm green"></span>
          </div>
          <span class="window-filename">auth --login</span>
          <span class="window-status"></span>
        </div>
        <div class="macos-card-body prompt-body">
          <span class="prompt-dollar">$</span>
          <input
            v-model="userIdInput"
            class="prompt-input"
            placeholder="user_id"
            @keydown.enter="submitUserId"
          />
          <button class="prompt-btn" :disabled="!userIdInput.trim()" @click="submitUserId">
            Enter
          </button>
        </div>
      </div>
    </div>

    <!-- ================================================================
         聊天界面
         ================================================================ -->
    <template v-else>
      <!-- 消息列表 -->
      <MessageList
        :messages="chatStore.messages"
        :is-streaming="chatStore.isStreaming"
      />

      <!-- 流式指示器 -->
      <StreamingIndicator
        :is-streaming="chatStore.isStreaming"
        :has-content="!!chatStore.lastMessage?.content"
      />

      <!-- 输入区 -->
      <ChatInput
        @send="handleSend"
      />
    </template>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

/* ---- user_id 设置 ---- */
.user-id-prompt {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: var(--space-32);
}

.prompt-card {
  width: 100%;
  max-width: 380px;
}

.prompt-body {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-20) var(--space-16);
}

.prompt-dollar {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--color-green);
  flex-shrink: 0;
}

.prompt-input {
  flex: 1;
  padding: var(--space-6) var(--space-8);
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  outline: none;
}

.prompt-input::placeholder {
  color: var(--color-text-tertiary);
}

.prompt-btn {
  padding: var(--space-6) var(--space-16);
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-md);
  background: var(--color-accent-muted);
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.prompt-btn:hover:not(:disabled) {
  background: var(--color-accent);
  color: #0a0a0a;
}

.prompt-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
