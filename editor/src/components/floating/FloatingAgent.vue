<!--
  Floating Agent window shell.

  Usage:
  The collapsed state keeps a compact prompt and native window controls. The
  expanded state renders the real AgentPanel in sidebar mode, so its message
  layout, responsive input, drawers, titlebar, and future component changes
  stay identical to the editor sidebar without a second UI implementation.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { fetchLLMConfig } from '@/api/settings'
import IcIcon from '@/components/common/IcIcon.vue'
import AgentPanel from '@/components/editor_workspace/AgentPanel.vue'
import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import { useChatStore, useSessionChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import type { ThemeMode } from '@/types/settings'

/** Transparent gutter leaves room for the native window's CSS shadow. */
const GUTTER = 20
const WINDOW_WIDTH = 420 + GUTTER * 2
const SIZES = { collapsed: 140, chat: 592 }
const ANIM_MS = 240
const ACTIVE_SESSION_KEY = 'agent_editor_active_session_id'
const PIN_MODE_LABELS: Record<string, string> = { off: '不置顶', normal: '普通置顶', global: '全局置顶' }

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = shallowRef(useChatStore())
const expanded = ref(false)
const currentHeight = ref(SIZES.collapsed)
const contextWindowTokens = ref(128000)
const modelConfigLabel = ref('配置模型')

const userId = computed(() => settingsStore.profile.userId)
const sessionTitle = computed(() => {
  const name = sessionStore.currentSession?.session_name || 'new session'
  return name.replace(/^标题:/, '').trim()
})

/** Animate Electron bounds because native setBounds has no CSS transition. */
let animFrame = 0
function animateHeightTo(target: number, duration = ANIM_MS) {
  cancelAnimationFrame(animFrame)
  const start = currentHeight.value
  const startedAt = performance.now()
  const step = (now: number) => {
    const progress = Math.min((now - startedAt) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    const height = Math.round(start + (target - start) * eased)
    currentHeight.value = height
    window.agentEditorDesktop?.floatingSetBounds({ width: WINDOW_WIDTH, height: height + GUTTER * 2 })
    if (progress < 1) animFrame = requestAnimationFrame(step)
  }
  animFrame = requestAnimationFrame(step)
}

/** Expand into the exact Agent sidebar-mode panel. */
function expand() {
  if (expanded.value) return
  expanded.value = true
  animateHeightTo(SIZES.chat)
}

/** Return to the prompt-only floating shell. */
function collapse() {
  if (!expanded.value) return
  expanded.value = false
  animateHeightTo(SIZES.collapsed)
}

/** Send from the collapsed prompt through the shared session-scoped store. */
async function sendMessage(text: string, reference = '') {
  if (!userId.value) return
  expand()
  if (!sessionStore.currentSessionId) {
    const sessionId = await sessionStore.create(userId.value)
    chatStore.value = useSessionChatStore(sessionId)
  }
  await chatStore.value.send(
    userId.value,
    sessionStore.currentSessionId,
    text,
    reference,
    settingsStore.agentLoopMode,
    settingsStore.agentAccessMode,
  )
}

/** Load the compact prompt label; AgentPanel loads its complete own state. */
async function loadModelConfig() {
  if (!userId.value) return
  try {
    const config = await fetchLLMConfig(userId.value)
    contextWindowTokens.value = config.context_window_tokens ?? 128000
    modelConfigLabel.value = config.model_name || '配置模型'
  } catch {
    modelConfigLabel.value = '配置模型'
  }
}

/** Keep the compact sender bound to the conversation selected in either window. */
function selectMirroredSession(sessionId: string, broadcast = false) {
  sessionStore.select(sessionId, broadcast)
  chatStore.value = useSessionChatStore(sessionId)
}

/** Apply window-shell state; AgentPanel handles its chat and titlebar settings. */
function handleWindowSync(payload: { type: string; value: unknown }) {
  if (payload.type === 'theme' && typeof payload.value === 'string') {
    settingsStore.setThemeMode(payload.value as ThemeMode, false)
  } else if (payload.type === 'session' && typeof payload.value === 'string') {
    selectMirroredSession(payload.value)
  }
}

/** Cycle the three Electron always-on-top modes. */
function cyclePinMode() {
  const next = settingsStore.floatingPinMode === 'off' ? 'normal'
    : settingsStore.floatingPinMode === 'normal' ? 'global' : 'off'
  settingsStore.setFloatingPinMode(next)
}

function handleClose() {
  window.agentEditorDesktop?.floatingClose()
}

function handleOpenInFull() {
  window.agentEditorDesktop?.openAgentPage()
}

watch(
  () => chatStore.value.isStreaming,
  (streaming) => { if (streaming) expand() },
)

watch(
  () => settingsStore.floatingPinMode,
  (mode) => { window.agentEditorDesktop?.floatingSetAlwaysOnTop(mode) },
)

let unsubscribeSync: (() => void) | undefined

onMounted(async () => {
  const storedSessionId = localStorage.getItem(ACTIVE_SESSION_KEY)
  if (storedSessionId) selectMirroredSession(storedSessionId, true)
  else if (userId.value) await sessionStore.load(userId.value)
  await loadModelConfig()
  window.agentEditorDesktop?.floatingSetAlwaysOnTop(settingsStore.floatingPinMode)
  unsubscribeSync = window.agentEditorDesktop?.onWindowSync?.(handleWindowSync)
  window.agentEditorDesktop?.floatingSetBounds({ width: WINDOW_WIDTH, height: SIZES.collapsed + GUTTER * 2 })
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animFrame)
  unsubscribeSync?.()
})
</script>

<template>
  <div class="floating-agent" :class="{ expanded }">
    <AgentPanel
      v-show="expanded"
      class="floating-agent-panel"
      mode="panel"
      panel-draggable
      @expand="handleOpenInFull"
    >
      <template #window-controls>
        <button class="floating-window-button" type="button" title="折叠为输入框" @click="collapse"><IcIcon name="unfold-less" :size="13" /></button>
        <button class="floating-window-button" :class="{ active: settingsStore.floatingPinMode !== 'off' }" type="button" :title="`置顶: ${PIN_MODE_LABELS[settingsStore.floatingPinMode] ?? '普通置顶'}`" @click="cyclePinMode">
          <svg height="12" viewBox="0 0 24 24" width="12" fill="currentColor"><path d="M16,9V4l1,0c0.55,0,1,-0.45,1,-1v0c0,-0.55,-0.45,-1,-1,-1L7,2C6.45,2,6,2.45,6,3v0c0,0.55,0.45,1,1,1l1,0v5c0,1.66,-1.34,3,-3,3v2h5.97v7l1,1l1,-1v-7H19v-2C17.34,12,16,10.66,16,9z" /></svg>
        </button>
        <button class="floating-window-button" type="button" title="关闭悬浮窗" @click="handleClose"><IcIcon name="close" :size="13" /></button>
      </template>
    </AgentPanel>

    <template v-if="!expanded">
      <header class="floating-topbar">
        <div class="topbar-title">{{ sessionTitle }}</div>
        <div class="topbar-actions">
          <button class="floating-window-button" type="button" title="展开会话" @click="expand"><IcIcon name="unfold" :size="13" /></button>
          <button class="floating-window-button" :class="{ active: settingsStore.floatingPinMode !== 'off' }" type="button" :title="`置顶: ${PIN_MODE_LABELS[settingsStore.floatingPinMode] ?? '普通置顶'}`" @click="cyclePinMode">
            <svg height="13" viewBox="0 0 24 24" width="13" fill="currentColor"><path d="M16,9V4l1,0c0.55,0,1,-0.45,1,-1v0c0,-0.55,-0.45,-1,-1,-1L7,2C6.45,2,6,2.45,6,3v0c0,0.55,0.45,1,1,1l1,0v5c0,1.66,-1.34,3,-3,3v2h5.97v7l1,1l1,-1v-7H19v-2C17.34,12,16,10.66,16,9z" /></svg>
          </button>
          <button class="floating-window-button" type="button" title="关闭悬浮窗" @click="handleClose"><IcIcon name="close" :size="13" /></button>
        </div>
      </header>
      <div class="collapsed-input">
        <ChatInput
          compact
          :disabled="!userId"
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
          @toggle-web-search="settingsStore.toggleWebSearch(!settingsStore.profile.webSearchEnabled)"
          @configure-model="() => {}"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.floating-agent {
  position: relative;
  display: flex;
  width: calc(100% - 40px);
  height: calc(100% - 40px);
  margin: 20px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-bg-app);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.32), 0 1px 3px rgba(0, 0, 0, 0.18);
}

.floating-agent-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.floating-topbar {
  -webkit-app-region: drag;
  position: absolute;
  inset: 0 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
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
  gap: 2px;
}

.floating-window-button {
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

.floating-window-button:hover {
  background: var(--color-primary-soft);
  color: var(--color-text);
}

.floating-window-button.active {
  color: var(--color-primary);
}

.collapsed-input {
  align-self: flex-end;
  width: 100%;
  padding: 32px 8px 8px;
}
</style>
