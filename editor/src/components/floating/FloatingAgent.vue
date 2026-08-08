<!--
  Floating Agent widget (two-state).

  Usage:
  Lives in the dedicated floating Electron window. Collapsed it is a single
  chat input with a minimal topbar; expanding animates the window taller and
  swaps in the Agent sidebar-mode titlebar (sessions drawer, task list, child
  agents, expand-to-full, new session, chat/tool mode), all backed by the real
  panel components. An empty session shows the Agent sidebar welcome area
  (two images + subtitle) with the input centered; the reused ChatInput keeps
  the sidebar-mode responsive layout (compact + centered) so the toolbar
  collapses on the narrow window. Session and theme are kept in sync with the
  main window over IPC (localStorage storage events do not cross Electron
  windows).
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import MessageList from '@/components/editor_workspace/agent_chat/MessageList.vue'
import SessionDrawer from '@/components/editor_workspace/agent_chat/SessionDrawer.vue'
import TaskListDrawer from '@/components/editor_workspace/agent_chat/TaskListDrawer.vue'
import ChildAgentPanel from '@/components/editor_workspace/agent_chat/ChildAgentPanel.vue'
import StreamingIndicator from '@/components/editor_workspace/agent_chat/StreamingIndicator.vue'
import LoaderCube from '@/components/editor_workspace/agent_chat/LoaderCube.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useTaskListStore } from '@/stores/taskList'
import { fetchLLMConfig } from '@/api/settings'
import type { ThemeMode } from '@/types/settings'
import darkTitle from '@/assets/images/暗色标题.png'
import lightTitle from '@/assets/images/亮色标题.png'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'

// Transparent gutter around the widget so its CSS shadow has room to render.
const GUTTER = 20
const WINDOW_WIDTH = 420 + GUTTER * 2
// Widget content height per state (window adds GUTTER on both sides).
const SIZES = {
  collapsed: 140,
  chat: 592,
}
const ANIM_MS = 240
const ACTIVE_SESSION_KEY = 'agent_editor_active_session_id'
const PIN_MODE_LABELS: Record<string, string> = { off: '不置顶', normal: '普通置顶', global: '全局置顶' }

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const taskListStore = useTaskListStore()

const expanded = ref(false)
// All window height changes are initiated here, so this mirror stays in sync.
const currentHeight = ref(SIZES.collapsed)
const sessionLoading = ref(false)
const contextWindowTokens = ref(128000)
const modelConfigLabel = ref('配置模型')
const messageListRef = ref<{ scrollToBottom: (opts?: ScrollToOptions) => void } | null>(null)
const isMessageListAtBottom = ref(true)
const sessionDrawerOpen = ref(false)
const taskListOpen = ref(false)
const childAgentOpen = ref(false)

const userId = computed(() => settingsStore.profile.userId)
const hasMessages = computed(() => chatStore.messages.filter((m) => m.role !== 'system').length > 0)
const sessionTitle = computed(() => {
  const name = sessionStore.currentSession?.session_name || 'new session'
  return name.replace(/^标题:/, '').trim()
})
const hasStreamingContent = computed(() => !!chatStore.lastMessage?.content)
const isDark = computed(() => settingsStore.isDark)
const welcomeTitleSrc = computed(() => isDark.value ? darkTitle : lightTitle)
const logoSrc = computed(() => isDark.value ? darkLogo : lightLogo)
const knowledgeTitle = computed(() => {
  const name = settingsStore.activeKnowledgeLibrary?.name?.trim()
  if (name) return name
  const parts = settingsStore.profile.knowledgeDir.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] || '未命名'
})

// Native setBounds has no CSS transition, so drive the window height with rAF
// + easeOutCubic, updating the bounds every frame.
let animFrame = 0
function animateHeightTo(target: number, duration = ANIM_MS) {
  cancelAnimationFrame(animFrame)
  const start = currentHeight.value
  const t0 = performance.now()
  const step = (now: number) => {
    const t = Math.min((now - t0) / duration, 1)
    const eased = 1 - Math.pow(1 - t, 3)
    const h = Math.round(start + (target - start) * eased)
    currentHeight.value = h
    window.agentEditorDesktop?.floatingSetBounds({ width: WINDOW_WIDTH, height: h + GUTTER * 2 })
    if (t < 1) {
      animFrame = requestAnimationFrame(step)
    }
  }
  animFrame = requestAnimationFrame(step)
}

function expand() {
  if (expanded.value) return
  expanded.value = true
  animateHeightTo(SIZES.chat)
}

function collapse() {
  if (!expanded.value) return
  // 折叠态只留输入框,关闭所有浮层面板
  sessionDrawerOpen.value = false
  taskListOpen.value = false
  childAgentOpen.value = false
  expanded.value = false
  animateHeightTo(SIZES.collapsed)
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
  // 只切换会话数据,不改变折叠形态
}

async function createNewSession() {
  if (!userId.value) return
  // 当前对话没有任何消息时不创建新对话,只收起会话抽屉
  if (!hasMessages.value) {
    sessionDrawerOpen.value = false
    return
  }
  await sessionStore.pruneEmpty(userId.value)
  const sessionId = await sessionStore.create(userId.value)
  await selectSession(sessionId)
  sessionDrawerOpen.value = false
}

function toggleTaskList() {
  taskListOpen.value = !taskListOpen.value
  if (taskListOpen.value && sessionStore.currentSessionId) {
    void taskListStore.load(sessionStore.currentSessionId)
  }
}

async function sendMessage(text: string, reference = '') {
  if (!userId.value) return
  expand()
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

function handleOpenInFull() {
  window.agentEditorDesktop?.openAgentPage()
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

// Keep chat expanded when streaming starts (e.g. suggestion from main window).
watch(
  () => chatStore.isStreaming,
  (streaming) => {
    if (streaming) expand()
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
  // Snap to the collapsed size on first mount.
  window.agentEditorDesktop?.floatingSetBounds({ width: WINDOW_WIDTH, height: SIZES.collapsed + GUTTER * 2 })
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animFrame)
  unsubscribeSync?.()
})
</script>

<template>
  <div class="floating-agent" :class="{ 'state-chat': expanded }">
    <!-- 展开态:Agent 侧边栏模式顶栏(agent-titlebar)。空白区可拖动窗口,按钮可点击 -->
    <header v-if="expanded" class="floating-titlebar">
      <button
        class="floating-top-btn"
        type="button"
        title="会话"
        @click="sessionDrawerOpen = !sessionDrawerOpen"
      >
        <IcIcon name="forum" :size="15" />
      </button>
      <div class="floating-title"><strong>{{ sessionTitle }}</strong></div>
      <div class="floating-title-actions">
        <button
          class="floating-top-btn"
          :class="{ active: taskListOpen }"
          type="button"
          title="任务列表"
          @click="toggleTaskList"
        >
          <IcIcon name="checklist" :size="15" />
        </button>
        <button
          class="floating-top-btn"
          :class="{ active: childAgentOpen }"
          type="button"
          title="子 Agent"
          @click="childAgentOpen = !childAgentOpen"
        >
          <IcIcon name="group" :size="15" />
        </button>
        <button class="floating-top-btn" type="button" title="展开 Agent 页面" @click="handleOpenInFull">
          <IcIcon name="open-in-full" :size="15" />
        </button>
        <button class="floating-top-btn" type="button" title="新建会话" @click="createNewSession">
          <IcIcon name="add-comment" :size="15" />
        </button>
        <button
          class="floating-top-btn"
          type="button"
          :title="`切换渲染模式: ${settingsStore.chatMode === 'chat' ? 'chat' : 'tool'}`"
          @click="settingsStore.toggleChatMode"
        >
          <IcIcon name="history" :size="14" />
        </button>
        <span class="floating-top-divider"></span>
        <button class="floating-top-btn" type="button" title="折叠为输入框" @click="collapse">
          <IcIcon name="unfold-less" :size="13" />
        </button>
        <button
          class="floating-top-btn"
          :class="{ 'pin-active': settingsStore.floatingPinMode !== 'off' }"
          type="button"
          :title="`置顶: ${PIN_MODE_LABELS[settingsStore.floatingPinMode] ?? '普通置顶'}`"
          @click="cyclePinMode"
        >
          <svg height="12" viewBox="0 0 24 24" width="12" fill="currentColor">
            <path d="M16,9V4l1,0c0.55,0,1,-0.45,1,-1v0c0,-0.55,-0.45,-1,-1,-1L7,2C6.45,2,6,2.45,6,3v0c0,0.55,0.45,1,1,1l1,0v5c0,1.66,-1.34,3,-3,3v2h5.97v7l1,1l1,-1v-7H19v-2C17.34,12,16,10.66,16,9z"></path>
          </svg>
        </button>
        <button class="floating-top-btn" type="button" title="关闭悬浮窗" @click="handleClose">
          <IcIcon name="close" :size="13" />
        </button>
      </div>
    </header>

    <!-- 折叠态:极简顶栏 -->
    <header v-else class="floating-topbar">
      <div class="topbar-title">{{ sessionTitle }}</div>
      <div class="topbar-actions">
        <button class="floating-top-btn" type="button" title="展开会话" @click="expand">
          <IcIcon name="unfold" :size="13" />
        </button>
        <button
          class="floating-top-btn"
          :class="{ 'pin-active': settingsStore.floatingPinMode !== 'off' }"
          type="button"
          :title="`置顶: ${PIN_MODE_LABELS[settingsStore.floatingPinMode] ?? '普通置顶'}`"
          @click="cyclePinMode"
        >
          <svg height="13" viewBox="0 0 24 24" width="13" fill="currentColor">
            <path d="M16,9V4l1,0c0.55,0,1,-0.45,1,-1v0c0,-0.55,-0.45,-1,-1,-1L7,2C6.45,2,6,2.45,6,3v0c0,0.55,0.45,1,1,1l1,0v5c0,1.66,-1.34,3,-3,3v2h5.97v7l1,1l1,-1v-7H19v-2C17.34,12,16,10.66,16,9z"></path>
          </svg>
        </button>
        <button class="floating-top-btn" type="button" title="关闭悬浮窗" @click="handleClose">
          <IcIcon name="close" :size="13" />
        </button>
      </div>
    </header>

    <!-- 会话抽屉(absolute 抽屉,盖在消息区上) -->
    <SessionDrawer
      :open="sessionDrawerOpen"
      :user-id="userId"
      @close="sessionDrawerOpen = false"
      @create="createNewSession"
      @select="selectSession"
    />

    <div class="floating-body">
      <div v-if="sessionLoading" class="history-loading">
        <LoaderCube />
        <span>加载会话历史...</span>
      </div>

      <template v-else>
        <Transition name="floating-fade">
          <div v-if="expanded" class="chat-scroll">
            <template v-if="hasMessages || chatStore.isStreaming">
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
            </template>
            <div v-else class="welcome-center">
              <img :src="logoSrc" class="welcome-cap-icon" alt="" />
              <img :src="welcomeTitleSrc" class="welcome-logo" alt="MetaWeave" />
              <p class="welcome-subtitle">在知识库 {{ knowledgeTitle }} 中有什么问题?</p>
            </div>
          </div>
        </Transition>

        <div class="input-wrap" :class="{ 'input-wrap-centered': expanded && !hasMessages && !chatStore.isStreaming }">
          <ChatInput
            :disabled="!userId"
            :centered="expanded && !hasMessages && !chatStore.isStreaming"
            :compact="true"
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
      </template>
    </div>

    <!-- 任务列表 / 子 Agent 面板(overlay 盖在消息区之上) -->
    <div class="floating-overlays">
      <div v-if="taskListOpen" class="floating-overlay-card">
        <TaskListDrawer @close="taskListOpen = false" />
      </div>
      <div v-if="childAgentOpen && sessionStore.currentSessionId" class="floating-overlay-card">
        <ChildAgentPanel :session-id="sessionStore.currentSessionId" @close="childAgentOpen = false" />
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
  --input-btn-bg: var(--color-surface);
  --input-send-disabled: var(--color-text-muted);
  --blur-strength: 10px;

  position: relative;
  display: flex;
  flex-direction: column;
  width: calc(100% - 40px);
  height: calc(100% - 40px);
  margin: 20px;
  overflow: hidden;
  border-radius: 28px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.32), 0 1px 3px rgba(0, 0, 0, 0.18);
}

/* 常驻顶栏(折叠态):整体可拖动窗口,按钮区域可点击,无下边框 */
.floating-topbar {
  -webkit-app-region: drag;
  flex-shrink: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 32px;
  padding: 0 var(--space-10);
}

.topbar-title {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 展开态:Agent 侧边栏模式顶栏(agent-titlebar),无下边框 */
.floating-titlebar {
  -webkit-app-region: drag;
  flex-shrink: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-6);
  min-height: 32px;
  padding: 0 var(--space-8);
}

.floating-title {
  min-width: 0;
}

.floating-title strong {
  display: block;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.floating-title-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.floating-top-divider {
  width: 1px;
  height: 14px;
  margin: 0 2px;
  background: var(--color-border);
}

.floating-top-btn {
  -webkit-app-region: no-drag;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.floating-top-btn:hover {
  background: var(--color-primary-soft);
  color: var(--color-text);
}

.floating-top-btn.active,
.floating-top-btn.pin-active {
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

/* 无消息空态:Agent 侧边栏同款欢迎区(两张图 + 欢迎词),bottom 定位使
   欢迎词底部刚好贴在居中输入框上方,与 AgentPanel 侧边栏视觉一致。 */
.welcome-center {
  position: absolute;
  bottom: calc(50% + 60px);
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  z-index: 1;
}

.welcome-cap-icon {
  display: block;
  width: 64px;
  height: auto;
  object-fit: contain;
  margin-bottom: 6px;
  pointer-events: auto;
  animation: welcome-cap-in 1.2s ease-out forwards;
}

.welcome-logo {
  display: block;
  width: 110px;
  height: auto;
  object-fit: contain;
  pointer-events: auto;
  animation: welcome-fade-in 1.2s ease-out forwards;
}

.welcome-subtitle {
  margin: var(--space-8) 0 0;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.5;
  text-align: center;
}

@keyframes welcome-cap-in {
  from {
    opacity: 0;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes welcome-fade-in {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
   so reserve the same height in flow to keep messages above it. When the input
   is centered (empty session) it floats instead, so drop the reservation and let
   the welcome area use the full body height. */
.floating-agent.state-chat .input-wrap {
  height: 100px;
}

.floating-agent.state-chat .input-wrap.input-wrap-centered {
  height: 0;
}

/* 任务列表 / 子 Agent overlay:盖住消息区,悬于 body 之上 */
.floating-overlays {
  position: absolute;
  top: 32px;
  right: 8px;
  bottom: 8px;
  left: 8px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.floating-overlay-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28);
  pointer-events: auto;
}

/* 展开/折叠时消息区淡入淡出 */
.floating-fade-enter-active,
.floating-fade-leave-active {
  transition: opacity 160ms ease;
}

.floating-fade-enter-from,
.floating-fade-leave-to {
  opacity: 0;
}
</style>
