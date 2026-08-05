<!--
  Floating Agent widget (two-state).

  Usage:
  Lives in the dedicated floating Electron window. In the collapsed state it is
  just a single centered chat input. Sending a message grows it into a compact
  chat that mirrors the main-window Agent panel session. Theme and session are
  kept in sync with the main window over IPC (localStorage storage events do not
  cross Electron windows).
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import MessageList from '@/components/editor_workspace/agent_chat/MessageList.vue'
import StreamingIndicator from '@/components/editor_workspace/agent_chat/StreamingIndicator.vue'
import LoaderCube from '@/components/editor_workspace/agent_chat/LoaderCube.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { fetchLLMConfig } from '@/api/settings'
import type { ThemeMode } from '@/types/settings'

type StateKind = 'collapsed' | 'chat'

// Transparent gutter around the widget so its CSS shadow has room to render.
const GUTTER = 20
const WINDOW_WIDTH = 420 + GUTTER * 2
// Widget content height per state (window adds GUTTER on both sides). The
// collapsed height (~128px) fits the 22px drag strip plus the ~92px ChatInput
// with the input vertically centered.
const SIZES: Record<StateKind, number> = {
  collapsed: 128,
  chat: 560,
}
const ACTIVE_SESSION_KEY = 'agent_editor_active_session_id'
const PIN_MODE_LABELS: Record<string, string> = { off: '不置顶', normal: '普通置顶', global: '全局置顶' }

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const state = ref<StateKind>('collapsed')
const sessionLoading = ref(false)
const contextWindowTokens = ref(128000)
const modelConfigLabel = ref('配置模型')
const messageListRef = ref<{ scrollToBottom: (opts?: ScrollToOptions) => void } | null>(null)
const isMessageListAtBottom = ref(true)

const userId = computed(() => settingsStore.profile.userId)
const hasMessages = computed(() => chatStore.messages.filter((m) => m.role !== 'system').length > 0)
const hasStreamingContent = computed(() => !!chatStore.lastMessage?.content)

function applyHeight(kind: StateKind) {
  window.agentEditorDesktop?.floatingSetBounds({ width: WINDOW_WIDTH, height: SIZES[kind] + GUTTER * 2 })
}

async function selectSession(sessionId: string) {
  sessionStore.select(sessionId)
  chatStore.clear()
  sessionLoading.value = true
  try {
    await chatStore.loadHistory(sessionId, userId.value)
  } finally {
    sessionLoading.value = false
  }
  if (chatStore.messages.filter((m) => m.role !== 'system').length > 0) {
    state.value = 'chat'
    applyHeight('chat')
  } else {
    state.value = 'collapsed'
    applyHeight('collapsed')
  }
}

async function sendMessage(text: string, reference = '') {
  if (!userId.value) return
  if (state.value !== 'chat') {
    state.value = 'chat'
    applyHeight('chat')
  }
  await chatStore.send(
    userId.value,
    sessionStore.currentSessionId,
    text,
    reference,
    settingsStore.agentLoopMode,
    settingsStore.agentAccessMode,
  )
}

async function loadModelConfig() {
  const uid = userId.value
  if (!uid) return
  try {
    const config = await fetchLLMConfig(uid)
    contextWindowTokens.value = config.context_window_tokens ?? 128000
    modelConfigLabel.value = config.model_name || '配置模型'
  } catch {
    modelConfigLabel.value = '配置模型'
  }
}

function handleToggleWebSearch() {
  settingsStore.toggleWebSearch(!settingsStore.profile.webSearchEnabled)
}

function handleMessageBottomChange(isAtBottom: boolean) {
  isMessageListAtBottom.value = isAtBottom
}

function jumpToMessageBottom() {
  messageListRef.value?.scrollToBottom()
}

function handleCancelStream() {
  chatStore.cancelStream()
}

function handleClose() {
  window.agentEditorDesktop?.floatingClose()
}

function cyclePinMode() {
  const next = settingsStore.floatingPinMode === 'off' ? 'normal'
    : settingsStore.floatingPinMode === 'normal' ? 'global' : 'off'
  settingsStore.setFloatingPinMode(next)
}

// Cross-window sync over IPC: theme + active session pushed from the main window.
function handleWindowSync(payload: { type: string; value: string | null }) {
  if (!payload) return
  if (payload.type === 'theme' && payload.value) {
    settingsStore.setThemeMode(payload.value as ThemeMode)
  } else if (payload.type === 'session' && payload.value && payload.value !== sessionStore.currentSessionId) {
    void selectSession(payload.value)
  }
}

// Keep chat height when streaming starts (e.g. suggestion triggered from main window).
watch(
  () => chatStore.isStreaming,
  (streaming) => {
    if (streaming && state.value !== 'chat') {
      state.value = 'chat'
      applyHeight('chat')
    }
  },
)

// Pin-mode changes propagate to the OS window.
watch(
  () => settingsStore.floatingPinMode,
  (mode) => {
    window.agentEditorDesktop?.floatingSetAlwaysOnTop(mode)
  },
)

async function ensureSession() {
  if (!userId.value) return
  const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
  if (stored) {
    sessionStore.select(stored)
    chatStore.clear()
    sessionLoading.value = true
    try {
      await chatStore.loadHistory(stored, userId.value)
    } finally {
      sessionLoading.value = false
    }
    if (chatStore.messages.filter((m) => m.role !== 'system').length > 0) {
      state.value = 'chat'
      applyHeight('chat')
    }
    return
  }
  if (!sessionStore.currentSessionId) {
    await sessionStore.load(userId.value)
  }
}

let unsubscribeSync: (() => void) | undefined

onMounted(async () => {
  await ensureSession()
  await loadModelConfig()
  window.agentEditorDesktop?.floatingSetAlwaysOnTop(settingsStore.floatingPinMode)
  unsubscribeSync = window.agentEditorDesktop?.onWindowSync?.(handleWindowSync)
  applyHeight(state.value)
})

onBeforeUnmount(() => {
  unsubscribeSync?.()
})
</script>

<template>
  <div class="floating-agent" :class="{ 'state-chat': state === 'chat' }">
    <!-- Drag region: transparent strip, controls appear on hover. -->
    <div class="drag-bar">
      <span class="drag-hint"></span>
      <button
        class="pin-mode-btn"
        type="button"
        :class="{ 'pin-active': settingsStore.floatingPinMode !== 'off' }"
        :title="`置顶: ${PIN_MODE_LABELS[settingsStore.floatingPinMode] ?? '普通置顶'}`"
        @click="cyclePinMode"
      >
        <svg height="13" viewBox="0 0 24 24" width="13" fill="currentColor">
          <path d="M16,9V4l1,0c0.55,0,1,-0.45,1,-1v0c0,-0.55,-0.45,-1,-1,-1L7,2C6.45,2,6,2.45,6,3v0c0,0.55,0.45,1,1,1l1,0v5c0,1.66,-1.34,3,-3,3v2h5.97v7l1,1l1,-1v-7H19v-2C17.34,12,16,10.66,16,9z"></path>
        </svg>
      </button>
      <button class="close-btn" type="button" title="关闭悬浮窗" @click="handleClose">
        <IcIcon name="close" :size="12" />
      </button>
    </div>

    <div class="floating-body">
      <!-- Loading history -->
      <div v-if="sessionLoading" class="history-loading">
        <LoaderCube />
        <span>加载会话历史...</span>
      </div>

      <!-- Chat list -->
      <div v-else-if="state === 'chat' && (hasMessages || chatStore.isStreaming)" class="chat-scroll">
        <MessageList
          ref="messageListRef"
          :messages="chatStore.messages"
          :is-streaming="chatStore.isStreaming"
          :merge-assistants="settingsStore.chatMode === 'chat'"
          :suggestion-overlay="false"
          @bottom-change="handleMessageBottomChange"
        />
        <StreamingIndicator :is-streaming="chatStore.isStreaming" :has-content="hasStreamingContent" />
        <p v-if="chatStore.streamError" class="stream-error">{{ chatStore.streamError }}</p>
        <button
          v-if="hasMessages && !isMessageListAtBottom"
          class="scroll-bottom-button"
          type="button"
          title="滚动到底部"
          @click="jumpToMessageBottom"
        >
          <svg height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M440-800v487L216-537l-56 57 320 320 320-320-56-57-224 224v-487h-80Z"></path>
          </svg>
        </button>
      </div>

      <div class="input-wrap">
        <ChatInput
          :disabled="!userId"
          :centered="false"
          :compact="state === 'collapsed'"
          :web-search-enabled="settingsStore.profile.webSearchEnabled"
          :model-label="modelConfigLabel"
          :agent-access-mode="settingsStore.agentAccessMode"
          :reference="''"
          :attachments="[]"
          :suggestions="[]"
          :suggestions-loading="false"
          :messages="chatStore.messages"
          :max-context-tokens="contextWindowTokens"
          :is-streaming="chatStore.isStreaming"
          @send="sendMessage"
          @toggle-web-search="handleToggleWebSearch"
          @configure-model="() => {}"
          @cancel-stream="handleCancelStream"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.floating-agent {
  /* Input-box variables normally defined by AgentPanel; required here so the
     reused ChatInput renders a solid card (not a transparent box). */
  --input-bg: var(--color-surface-raised);
  --input-border: var(--color-border);
  --input-text: var(--color-text);
  --input-placeholder: var(--color-text-muted);
  --blur-strength: 10px;

  position: relative;
  display: flex;
  flex-direction: column;
  width: calc(100% - 40px);
  height: calc(100% - 40px);
  margin: 20px;
  overflow: hidden;
  border-radius: 16px;
  background: var(--color-surface);
  /* 1px 细描边:暗色下卡片与阴影同色系会被感知成"隔膜",
     描边把卡片轮廓分离出来;阴影收窄聚焦成投影而非铺满窗口的散光 */
  border: 1px solid var(--color-border);
  /* 阴影完全收在 20px gutter 内(最大扩散 ~10px),不会触到窗口边缘被裁切,
     暗色下就不会在卡片外围留下一圈被裁切的深色边缘 */
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.32), 0 1px 3px rgba(0, 0, 0, 0.18);
}

.drag-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  height: 20px;
  padding: 0 6px;
  -webkit-app-region: drag;
  opacity: 0;
  transition: opacity 150ms ease;
}

.floating-agent:hover .drag-bar {
  opacity: 1;
}

.drag-hint {
  flex: 1;
  height: 100%;
}

.pin-mode-btn,
.close-btn {
  -webkit-app-region: no-drag;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.pin-mode-btn:hover,
.close-btn:hover {
  background: var(--color-primary-soft);
  color: var(--color-text);
}

.pin-active {
  color: var(--color-primary);
}

.floating-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 8px 8px;
}

.history-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.stream-error {
  margin: 4px 0 0;
  color: var(--color-accent);
  font-size: calc(11px * var(--font-scale));
}

.scroll-bottom-button {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
}

.scroll-bottom-button:hover {
  color: var(--color-text);
}

.input-wrap {
  flex-shrink: 0;
  padding-top: 4px;
}

/* In chat state the input is absolutely positioned over the bottom of the body,
   so reserve the same height in flow to keep messages above it. */
.floating-agent.state-chat .input-wrap {
  height: 100px;
}
</style>
