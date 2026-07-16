<!--
  Right-side Agent panel.

  Usage:
  Hosts the editor Agent chat. It reuses the console chat/session backend and
  keeps observability and settings outside of the editor side panel.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { History, Maximize2, MessageSquarePlus, MessagesSquare, PanelLeft } from 'lucide-vue-next'

import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import MessageList from '@/components/editor_workspace/agent_chat/MessageList.vue'
import SessionDrawer from '@/components/editor_workspace/agent_chat/SessionDrawer.vue'
import StreamingIndicator from '@/components/editor_workspace/agent_chat/StreamingIndicator.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import SplitText from './SplitText.vue'
import type { AgentLoopMode } from '@/api/agent'

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const workspaceStore = useWorkspaceStore()
const props = withDefaults(defineProps<{
  mode?: 'panel' | 'page'
}>(), {
  mode: 'panel',
})
const emit = defineEmits<{
  expand: []
}>()
const sessionDrawerOpen = ref(props.mode === 'page')
const isBootstrapping = ref(false)
const referenceText = ref('')

const userId = computed(() => settingsStore.profile.userId)
const isDark = computed(() => settingsStore.isDark)
const hasMessages = computed(() => chatStore.messages.filter((m) => m.role !== 'system').length > 0)
const hasStreamingContent = computed(() => !!chatStore.lastMessage?.content)
const sessionTitle = computed(() => {
  const name = sessionStore.currentSession?.session_name || 'new session'
  return name.replace(/^标题:/, '').trim()
})
const chatModeLabel = computed(() => settingsStore.chatMode === 'chat' ? 'chat' : 'tool')
const knowledgeTitle = computed(() => {
  const name = settingsStore.activeKnowledgeLibrary?.name?.trim()
  if (name) return name
  const parts = settingsStore.profile.knowledgeDir.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] || '未命名'
})

async function reloadSessions() {
  if (!userId.value) {
    sessionStore.clearSelection()
    chatStore.clear()
    return
  }
  isBootstrapping.value = true
  try {
    await sessionStore.load(userId.value)
  } finally {
    isBootstrapping.value = false
  }
}

async function createSession() {
  if (!userId.value) {
    return
  }
  const sessionId = await sessionStore.create(userId.value)
  await selectSession(sessionId)
  if (props.mode !== 'page') {
    sessionDrawerOpen.value = false
  }
}

async function selectSession(sessionId: string) {
  sessionStore.select(sessionId)
  chatStore.clear()
  await chatStore.loadHistory(sessionId, userId.value)
}

async function sendMessage(text: string, reference = '') {
  if (!userId.value) {
    return
  }
  await chatStore.send(userId.value, sessionStore.currentSessionId, text, reference, settingsStore.agentLoopMode)
}

function clearReference() {
  referenceText.value = ''
}

function handleToggleWebSearch() {
  settingsStore.toggleWebSearch(!settingsStore.profile.webSearchEnabled)
}

function setAgentLoopMode(mode: AgentLoopMode) {
  settingsStore.setAgentLoopMode(mode)
}

function openSessionDrawer() {
  sessionDrawerOpen.value = true
}

function closeSessionDrawer() {
  sessionDrawerOpen.value = false
}

watch(userId, () => void reloadSessions())

watch(
  () => props.mode,
  (mode) => {
    if (mode === 'page') {
      sessionDrawerOpen.value = true
    }
  },
)

watch(() => workspaceStore.pendingAgentPrompt, (prompt) => {
  if (prompt) {
    void sendMessage(prompt)
    workspaceStore.pendingAgentPrompt = ''
  }
})

watch(() => workspaceStore.pendingAgentReference, (refText) => {
  if (refText) {
    referenceText.value = refText
    workspaceStore.agentSidebarOpen = true
    workspaceStore.pendingAgentReference = ''
  }
})

onMounted(() => {
  void reloadSessions()
  void settingsStore.fetchWebSearchSettings()
})
</script>

<template>
  <aside
    class="agent-panel console-chat-skin surface-panel"
    :class="{
      'theme-dark': isDark,
      'theme-light': !isDark,
      'agent-page-mode': props.mode === 'page',
    }"
  >
    <header v-if="props.mode === 'page'" class="agent-topbar">
      <div class="topbar-left">
        <button class="icon-button" type="button" title="New session" @click="createSession">
          <MessageSquarePlus :size="18" />
        </button>
        <button class="icon-button" type="button" title="Toggle sidebar" @click="sessionDrawerOpen = !sessionDrawerOpen">
          <PanelLeft :size="18" />
        </button>
      </div>
      <span class="topbar-title">{{ sessionTitle }}</span>
      <div class="topbar-right"></div>
    </header>

    <div class="agent-body">
      <SessionDrawer
        :open="sessionDrawerOpen"
        :mode="props.mode"
        :user-id="userId"
        :chat-mode-label="chatModeLabel"
        @close="closeSessionDrawer"
        @create="createSession"
        @select="selectSession"
        @toggle-chat-mode="settingsStore.toggleChatMode"
      />

      <button
        v-if="props.mode === 'page' && !sessionDrawerOpen"
        class="drawer-hover-zone"
        type="button"
        title="Open sessions"
        aria-label="Open sessions"
        @mouseenter="openSessionDrawer"
        @focus="openSessionDrawer"
      ></button>

      <header v-if="props.mode === 'panel'" class="agent-titlebar">
      <button
        class="icon-button drawer-toggle"
        type="button"
        title="Open sessions"
        @click="sessionDrawerOpen = !sessionDrawerOpen"
      >
        <MessagesSquare :size="16" />
      </button>
      <div class="title-meta">
        <strong>{{ sessionTitle }}</strong>
      </div>
      <div class="title-actions">
        <button
          v-if="props.mode === 'panel'"
          class="icon-button"
          type="button"
          title="Expand Agent page"
          @click="emit('expand')"
        >
          <Maximize2 :size="16" />
        </button>
        <button class="icon-button" type="button" title="New session" @click="createSession">
          <MessageSquarePlus :size="16" />
        </button>
        <button class="mode-button" type="button" title="Toggle chat render mode" @click="settingsStore.toggleChatMode">
          <History :size="15" />
          <span>{{ chatModeLabel }}</span>
        </button>
      </div>
    </header>

    <main class="chat-body" :class="{ dimmed: isBootstrapping }">
      <Transition name="welcome-fade">
        <div v-if="!hasMessages && !chatStore.isStreaming" class="welcome-center">
          <SplitText text="MetaWeave" tag="h1" class="welcome-title" :trigger-on-mount="true" />
          <p class="welcome-subtitle">在知识库 {{ knowledgeTitle }} 中有什么问题?</p>
        </div>
      </Transition>
      <MessageList
        :messages="chatStore.messages"
        :is-streaming="chatStore.isStreaming"
        :merge-assistants="settingsStore.chatMode === 'chat'"
      />
      <StreamingIndicator :is-streaming="chatStore.isStreaming" :has-content="hasStreamingContent" />
      <p v-if="chatStore.streamError" class="stream-error">{{ chatStore.streamError }}</p>
      <ChatInput
        :disabled="!userId"
        :centered="!hasMessages && !chatStore.isStreaming"
        :web-search-enabled="settingsStore.profile.webSearchEnabled"
        :agent-mode="settingsStore.agentLoopMode"
        :reference="referenceText"
        @send="sendMessage"
        @toggle-web-search="handleToggleWebSearch"
        @set-agent-mode="setAgentLoopMode"
        @clear-reference="clearReference"
      />
    </main>
    </div>
  </aside>
</template>

<style scoped>
.agent-panel {
  --font-chat: var(--font-ui);
  --font-mono: var(--font-code);
  --font-size-xs: 11px;
  --font-size-sm: 13px;
  --font-size-md: 15px;
  --font-size-lg: 18px;
  --font-size-xl: 22px;
  --line-height-relaxed: 1.65;
  --line-height-tight: 1.25;
  --font-weight-semibold: 650;
  --color-bg-elevated: var(--color-canvas-soft);
  --color-bg-muted: var(--color-canvas);
  --color-bg-hover: rgba(66, 36, 235, 0.13);
  --color-text-primary: var(--color-text);
  --color-text-secondary: var(--color-text-secondary);
  --color-text-tertiary: var(--color-text-muted);
  --color-border-light: rgba(255, 255, 255, 0.08);
  --color-accent: var(--color-primary);
  --color-accent-hover: var(--color-primary-hover);
  --color-accent-muted: var(--color-primary-soft);
  --color-blue: var(--color-primary);
  /* User bubble: red accent */
  --color-user-bubble: rgba(235, 36, 99, 0.14);
  --color-user-bubble-border: rgba(235, 36, 99, 0.42);
  --color-user-bubble-highlight: rgba(255, 255, 255, 0.06);
  --color-user-bubble-glow: rgba(235, 36, 99, 0.18);
  /* Agent bubble: blue primary */
  --color-agent-bubble: rgba(66, 36, 235, 0.12);
  --color-agent-bubble-border: rgba(66, 36, 235, 0.38);
  --color-agent-bubble-highlight: rgba(255, 255, 255, 0.08);
  --color-agent-bubble-glow: rgba(66, 36, 235, 0.14);
  --input-bg: var(--color-surface-raised);
  --input-border: var(--color-border);
  --input-text: var(--color-text);
  --input-placeholder: var(--color-text-muted);
  --input-btn-bg: var(--color-surface);
  --input-send-disabled: var(--color-text-muted);
  --blur-strength: 10px;
  --radius-xl: 18px;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 0;
  border-right: 0;
  border-bottom: 0;
  border-radius: 0;
  background: var(--color-canvas-soft);
}

.agent-panel.agent-page-mode {
  --agent-chat-max-width: min(34vw, 640px);
  --agent-topbar-height: 48px;
  border: 0;
  background: transparent;
  backdrop-filter: none;
}

.agent-panel.theme-light {
  --color-user-bubble: rgba(235, 36, 99, 0.10);
  --color-user-bubble-glow: rgba(235, 36, 99, 0.10);
  --color-agent-bubble: rgba(66, 36, 235, 0.08);
  --color-agent-bubble-glow: rgba(66, 36, 235, 0.08);
}

.agent-titlebar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 42px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-muted);
}

.agent-topbar {
  display: flex;
  align-items: center;
  min-height: var(--agent-topbar-height, 48px);
  padding: 0 var(--space-12);
  gap: var(--space-8);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.topbar-title {
  flex: 1;
  overflow: hidden;
  text-align: center;
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 68px;
}

.agent-body {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.drawer-toggle {
  width: 28px;
  height: 26px;
  border-radius: var(--radius-sm);
}

.title-meta {
  min-width: 0;
}

.title-meta strong {
  display: block;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-actions {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.icon-button,
.mode-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text-tertiary);
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.icon-button {
  width: 28px;
  border-radius: 999px;
  border: none;
}

.mode-button {
  gap: var(--space-4);
  padding: 0 var(--space-8);
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 10px;
}

.icon-button:hover,
.mode-button:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
}

.chat-body {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  transition: opacity var(--transition-fast);
}

.agent-page-mode :deep(.message-list) {
  width: min(100%, var(--agent-chat-max-width));
  align-self: center;
  padding-right: 0;
  padding-left: 0;
}

.agent-page-mode :deep(.bubble-row) {
  max-width: 100%;
}

.agent-page-mode :deep(.chat-input-wrap) {
  max-width: var(--agent-chat-max-width);
}

.agent-page-mode .stream-error {
  width: min(100%, var(--agent-chat-max-width));
  margin-right: auto;
  margin-left: auto;
}

.drawer-hover-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 3;
  width: 18px;
  border: 0;
  background: linear-gradient(90deg, rgba(66, 36, 235, 0.18), transparent);
  opacity: 0.18;
}

.drawer-hover-zone:hover {
  opacity: 0.42;
}

.agent-page-mode .welcome-center {
  right: 50%;
  left: auto;
  width: min(100%, var(--agent-chat-max-width));
  transform: translateX(50%);
}

.chat-body.dimmed {
  opacity: 0.55;
  pointer-events: none;
}

.stream-error {
  margin: 0 var(--space-16) var(--space-8);
  padding: var(--space-8) var(--space-10);
  border: 1px solid rgba(235, 36, 99, 0.36);
  background: rgba(235, 36, 99, 0.08);
  color: #f08aa9;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.welcome-center {
  position: absolute;
  bottom: calc(50% + 100px);
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  z-index: 1;
}

.welcome-title {
  margin: 0;
  color: var(--color-text);
  font-family: "Monocraft", var(--font-code);
  font-size: 32px;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.welcome-subtitle {
  margin: var(--space-10) 0 0;
  color: var(--color-text-muted);
  font-size: 14px;
  line-height: 1.5;
}

.welcome-fade-leave-active {
  transition:
    opacity 250ms ease,
    transform 250ms ease;
}

.welcome-fade-leave-to {
  opacity: 0;
  transform: translateY(-16px);
}

@media (max-width: 820px) {
  .agent-panel.agent-page-mode {
    --agent-chat-max-width: min(92vw, 560px);
  }

  .mode-button span {
    display: none;
  }
}
</style>
