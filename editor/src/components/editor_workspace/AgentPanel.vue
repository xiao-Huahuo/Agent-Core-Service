<!--
  Right-side Agent panel.

  Usage:
  Hosts the editor Agent chat. It reuses the console chat/session backend and
  keeps observability and settings outside of the editor side panel.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ChevronDown, History, Maximize2, MessageSquarePlus, MessagesSquare, PanelLeft, UploadCloud } from 'lucide-vue-next'

import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import MessageList from '@/components/editor_workspace/agent_chat/MessageList.vue'
import SessionDrawer from '@/components/editor_workspace/agent_chat/SessionDrawer.vue'
import StreamingIndicator from '@/components/editor_workspace/agent_chat/StreamingIndicator.vue'
import { useChatStore } from '@/stores/chat'
import type { AgentUploadedAttachment } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import SplitText from './SplitText.vue'
import type { AgentLoopMode } from '@/api/agent'
import { uploadAgentAttachment } from '@/api/agent'

type MessageListApi = {
  scrollToBottom: (options?: ScrollToOptions) => void
}

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
const messageListRef = ref<MessageListApi | null>(null)
const isMessageListAtBottom = ref(true)
const dragDepth = ref(0)
const isUploadingAttachment = ref(false)
const uploadStatusText = ref('')
const welcomeIconUrl = new URL('../../assets/images/无底图标.png', import.meta.url).href
const modeSwitchRef = ref<HTMLElement | null>(null)
const modeIndicatorStyle = computed(() => {
  if (settingsStore.chatMode === 'chat') {
    return { width: 'calc(50% - 2px)', transform: 'translateX(0)' }
  }
  return { width: 'calc(50% - 2px)', transform: 'translateX(calc(100% + 0px))' }
})

const userId = computed(() => settingsStore.profile.userId)
const isDark = computed(() => settingsStore.isDark)
const hasMessages = computed(() => chatStore.messages.filter((m) => m.role !== 'system').length > 0)
const hasStreamingContent = computed(() => !!chatStore.lastMessage?.content)
const isAttachmentDropActive = computed(() => dragDepth.value > 0 || isUploadingAttachment.value)
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
  // 当前对话没有任何消息时不创建新对话，只收起侧边栏
  if (!chatStore.messages.some((m) => m.role !== 'system')) {
    if (props.mode !== 'page') {
      sessionDrawerOpen.value = false
    }
    return
  }
  // 先清理之前堆积的空会话，再创建新的
  await sessionStore.pruneEmpty(userId.value)
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

function setChatRenderMode(mode: 'chat' | 'tool') {
  if (settingsStore.chatMode !== mode) {
    settingsStore.toggleChatMode()
  }
}

function openSessionDrawer() {
  sessionDrawerOpen.value = true
}

function closeSessionDrawer() {
  sessionDrawerOpen.value = false
}

function handleMessageBottomChange(isAtBottom: boolean) {
  isMessageListAtBottom.value = isAtBottom
}

function jumpToMessageBottom() {
  messageListRef.value?.scrollToBottom({ behavior: 'smooth' })
  isMessageListAtBottom.value = true
}

function removeAttachment(attachment: AgentUploadedAttachment) {
  void chatStore.deleteAttachment(attachment)
}

function containsFiles(event: DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

function handleDragEnter(event: DragEvent) {
  if (!containsFiles(event)) return
  event.preventDefault()
  dragDepth.value += 1
}

function handleDragOver(event: DragEvent) {
  if (!containsFiles(event)) return
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

function handleDragLeave(event: DragEvent) {
  if (!containsFiles(event)) return
  event.preventDefault()
  dragDepth.value = Math.max(0, dragDepth.value - 1)
}

async function handleDrop(event: DragEvent) {
  if (!containsFiles(event)) return
  event.preventDefault()
  dragDepth.value = 0
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (!files.length || !userId.value) {
    return
  }
  let targetSessionId = sessionStore.currentSessionId
  if (!targetSessionId) {
    targetSessionId = await sessionStore.create(userId.value)
    sessionStore.select(targetSessionId)
  }
  await uploadFiles(files, targetSessionId)
}

async function handleFileSelect(file: File) {
  if (!userId.value) return
  let targetSessionId = sessionStore.currentSessionId
  if (!targetSessionId) {
    targetSessionId = await sessionStore.create(userId.value)
    sessionStore.select(targetSessionId)
  }
  await uploadFiles([file], targetSessionId)
}

async function uploadFiles(files: File[], sessionId: string) {
  isUploadingAttachment.value = true
  try {
    for (const [index, file] of files.entries()) {
      uploadStatusText.value = `Uploading ${index + 1}/${files.length}: ${file.name}`
      const response = await uploadAgentAttachment(userId.value!, sessionId, file)
      chatStore.addPendingAttachment(response.attachment)
    }
    const firstUploadedFile = files[0]
    uploadStatusText.value = files.length === 1 && firstUploadedFile
      ? `Uploaded ${firstUploadedFile.name}`
      : `Uploaded ${files.length} files`
    window.setTimeout(() => {
      if (!isUploadingAttachment.value) uploadStatusText.value = ''
    }, 1600)
  } catch (error) {
    uploadStatusText.value = error instanceof Error ? error.message : 'Upload failed'
  } finally {
    isUploadingAttachment.value = false
  }
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
      'agent-drawer-open': props.mode === 'page' && sessionDrawerOpen,
      'attachment-drop-active': isAttachmentDropActive,
    }"
    @dragenter="handleDragEnter"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <Transition name="attachment-drop-fade">
      <div v-if="isAttachmentDropActive" class="attachment-drop-overlay" aria-live="polite">
        <UploadCloud :size="38" />
        <span>{{ uploadStatusText || 'Drop files to attach to this session' }}</span>
      </div>
    </Transition>

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
      <div class="topbar-right">
        <div ref="modeSwitchRef" class="topbar-mode-switch" role="group" aria-label="Chat render mode">
          <span class="mode-indicator" :style="modeIndicatorStyle"></span>
          <button
            class="topbar-mode-option"
            :class="{ active: settingsStore.chatMode === 'chat' }"
            type="button"
            aria-label="Chat mode"
            :aria-pressed="settingsStore.chatMode === 'chat'"
            @click="setChatRenderMode('chat')"
          >
            Chat
          </button>
          <button
            class="topbar-mode-option"
            :class="{ active: settingsStore.chatMode === 'tool' }"
            type="button"
            aria-label="Tool mode"
            :aria-pressed="settingsStore.chatMode === 'tool'"
            @click="setChatRenderMode('tool')"
          >
            Tool
          </button>
        </div>
      </div>
    </header>

    <div class="agent-body">
      <SessionDrawer
        :open="sessionDrawerOpen"
        :mode="props.mode"
        :user-id="userId"
        @close="closeSessionDrawer"
        @create="createSession"
        @select="selectSession"
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
          <img class="welcome-icon" :src="welcomeIconUrl" alt="" aria-hidden="true" />
          <SplitText text="MetaWeave" tag="h1" class="welcome-title" :trigger-on-mount="true" />
          <p class="welcome-subtitle">在知识库 {{ knowledgeTitle }} 中有什么问题?</p>
        </div>
      </Transition>
      <MessageList
        ref="messageListRef"
        :messages="chatStore.messages"
        :is-streaming="chatStore.isStreaming"
        :merge-assistants="settingsStore.chatMode === 'chat'"
        @bottom-change="handleMessageBottomChange"
      />
      <StreamingIndicator :is-streaming="chatStore.isStreaming" :has-content="hasStreamingContent" />
      <p v-if="chatStore.streamError" class="stream-error">{{ chatStore.streamError }}</p>
      <button
        v-if="hasMessages && !isMessageListAtBottom"
        class="scroll-bottom-button"
        type="button"
        title="Scroll to bottom"
        aria-label="Scroll to bottom"
        @click="jumpToMessageBottom"
      >
        <ChevronDown :size="18" />
      </button>
      <div v-if="chatStore.isStreaming" class="thinking-flow" aria-live="polite">
        <span>正在思考</span>
      </div>
      <ChatInput
        :disabled="!userId"
        :centered="!hasMessages && !chatStore.isStreaming"
        :web-search-enabled="settingsStore.profile.webSearchEnabled"
        :agent-mode="settingsStore.agentLoopMode"
        :reference="referenceText"
        :attachments="chatStore.pendingAttachments"
        @send="sendMessage"
        @toggle-web-search="handleToggleWebSearch"
        @set-agent-mode="setAgentLoopMode"
        @clear-reference="clearReference"
        @remove-attachment="removeAttachment"
        @file-select="handleFileSelect"
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
  --color-bg-hover: var(--color-primary-soft);
  --color-text-primary: var(--color-text);
  --color-text-secondary: var(--color-text-secondary);
  --color-text-tertiary: var(--color-text-muted);
  --color-border-light: rgba(255, 255, 255, 0.08);
  --color-accent: var(--color-primary);
  --color-accent-hover: var(--color-primary-hover);
  --color-accent-muted: var(--color-primary-soft);
  --color-blue: var(--color-primary);
  --color-user-bubble: var(--color-primary-soft);
  --color-user-bubble-border: color-mix(in srgb, var(--color-primary) 46%, transparent);
  --color-user-bubble-highlight: rgba(255, 255, 255, 0.08);
  --color-user-bubble-glow: var(--color-primary-softer);
  --color-agent-bubble: var(--color-primary-soft);
  --color-agent-bubble-border: color-mix(in srgb, var(--color-primary) 38%, transparent);
  --color-agent-bubble-highlight: rgba(255, 255, 255, 0.08);
  --color-agent-bubble-glow: var(--color-primary-softer);
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
  border: 0;
  border-radius: 0;
  background: var(--color-canvas-soft);
}

.agent-panel.agent-page-mode {
  --agent-drawer-width: 280px;
  --agent-content-offset: 0px;
  --agent-chat-max-width: min(72vw, 960px);
  --agent-input-max-width: min(52vw, 720px);
  --agent-topbar-height: 32px;
  border: 0;
  background: var(--color-canvas-soft);
  backdrop-filter: none;
}

.agent-panel.agent-page-mode.agent-drawer-open {
  --agent-content-offset: var(--agent-drawer-width);
  --agent-chat-max-width: min(calc(100vw - var(--agent-content-offset) - 48px), 960px);
  --agent-input-max-width: min(calc(100vw - var(--agent-content-offset) - 96px), 720px);
}

.agent-panel.attachment-drop-active {
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 58%, transparent),
    inset 0 0 80px color-mix(in srgb, var(--color-accent) 18%, transparent);
}

.agent-titlebar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 28px;
  padding: 0 var(--space-10);
  background: var(--color-bg-muted);
}

.agent-topbar {
  display: flex;
  align-items: center;
  min-height: var(--agent-topbar-height, 32px);
  padding: 0 var(--space-12);
  gap: var(--space-8);
  background: var(--color-canvas-soft);
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
  justify-content: flex-end;
  gap: var(--space-4);
  min-width: 128px;
}

.topbar-mode-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
}

.mode-indicator {
  position: absolute;
  top: 2px;
  left: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary);
  transition:
    transform 200ms cubic-bezier(0.4, 0, 0.2, 1),
    width 200ms cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: none;
}

.topbar-mode-option {
  position: relative;
  z-index: 1;
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  height: 22px;
  padding: 0 var(--space-10);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: 10px;
  line-height: 1;
  cursor: pointer;
  transition:
    color var(--transition-fast);
}

.topbar-mode-option:hover {
  color: var(--color-text-secondary);
}

.topbar-mode-option.active {
  color: #ffffff;
}

.agent-body {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.attachment-drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 80;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-12);
  border: 1px dashed color-mix(in srgb, var(--color-accent) 68%, transparent);
  border-radius: inherit;
  background:
    radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--color-accent) 18%, transparent), transparent 38%),
    color-mix(in srgb, var(--color-surface-raised) 90%, transparent);
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: 13px;
  text-align: center;
  pointer-events: none;
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 32%, transparent),
    inset 0 0 120px rgba(0, 0, 0, 0.22),
    0 24px 80px rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(16px);
}

.attachment-drop-overlay svg {
  color: var(--color-accent);
}

.attachment-drop-fade-enter-active,
.attachment-drop-fade-leave-active {
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.attachment-drop-fade-enter-from,
.attachment-drop-fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
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
  font-family: var(--font-ui);
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
  box-sizing: border-box;
  width: 100%;
  align-self: stretch;
  padding-right: max(var(--space-16), calc((100% - var(--agent-content-offset) - var(--agent-chat-max-width)) / 2));
  padding-left: max(var(--space-16), calc(var(--agent-content-offset) + (100% - var(--agent-content-offset) - var(--agent-chat-max-width)) / 2));
  transition:
    padding-right 200ms ease,
    padding-left 200ms ease;
}

.agent-page-mode :deep(.bubble-row) {
  max-width: min(100%, 760px);
}

.agent-page-mode :deep(.tool-assistant-row) {
  width: 100%;
  max-width: 100%;
}

.agent-page-mode :deep(.chat-input-wrap) {
  left: calc(var(--agent-content-offset) + (100% - var(--agent-content-offset)) / 2);
  max-width: var(--agent-input-max-width);
  transition:
    left 200ms ease,
    bottom 350ms cubic-bezier(0.4, 0, 0.2, 1),
    width 350ms cubic-bezier(0.4, 0, 0.2, 1);
}

.agent-page-mode .stream-error {
  width: min(100%, var(--agent-chat-max-width));
  margin-right: max(var(--space-16), calc((100% - var(--agent-content-offset) - var(--agent-chat-max-width)) / 2));
  margin-left: max(var(--space-16), calc(var(--agent-content-offset) + (100% - var(--agent-content-offset) - var(--agent-chat-max-width)) / 2));
}

.scroll-bottom-button {
  position: absolute;
  left: 50%;
  bottom: 132px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
  transform: translateX(-50%);
  transition:
    left 200ms ease,
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.scroll-bottom-button:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
}

.agent-page-mode .scroll-bottom-button {
  left: calc(var(--agent-content-offset) + (100% - var(--agent-content-offset)) / 2);
}

.thinking-flow {
  position: absolute;
  left: var(--space-16);
  bottom: 112px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  height: 24px;
  pointer-events: none;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: 13px;
  letter-spacing: 0;
}

.thinking-flow span {
  background: linear-gradient(
    90deg,
    var(--color-text-tertiary) 0%,
    var(--color-text-primary) 34%,
    var(--color-accent) 50%,
    var(--color-text-primary) 66%,
    var(--color-text-tertiary) 100%
  );
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: thinking-shimmer 1.35s ease-in-out infinite alternate;
}

.agent-page-mode .thinking-flow {
  left: max(var(--space-16), calc(var(--agent-content-offset) + (100% - var(--agent-content-offset) - var(--agent-input-max-width)) / 2));
}

.drawer-hover-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 3;
  width: 18px;
  border: 0;
  background: linear-gradient(90deg, color-mix(in srgb, var(--color-primary) 18%, transparent), transparent);
  opacity: 0.18;
}

.drawer-hover-zone:hover {
  opacity: 0.42;
}

.agent-page-mode .welcome-center {
  right: calc((100% - var(--agent-content-offset)) / 2);
  left: auto;
  width: min(100%, var(--agent-chat-max-width));
  transform: translateX(50%);
  transition: right 200ms ease;
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
  font-family: var(--font-ui);
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

.welcome-icon {
  width: clamp(72px, 11vw, 112px);
  height: auto;
  margin-bottom: var(--space-14);
  object-fit: contain;
  opacity: 0;
  filter: drop-shadow(0 16px 34px color-mix(in srgb, var(--color-primary) 22%, transparent));
  animation: welcome-icon-reveal 900ms cubic-bezier(0.22, 1, 0.36, 1) 120ms forwards;
}

.welcome-title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-ui);
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

@keyframes thinking-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

@keyframes welcome-icon-reveal {
  0% {
    opacity: 0;
    transform: translateY(18px) scale(0.94);
  }
  60% {
    opacity: 1;
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 820px) {
  .agent-panel.agent-page-mode {
    --agent-content-offset: 0px;
    --agent-chat-max-width: min(92vw, 560px);
    --agent-input-max-width: min(92vw, 560px);
  }

  .agent-panel.agent-page-mode.agent-drawer-open {
    --agent-content-offset: 0px;
    --agent-chat-max-width: min(92vw, 560px);
    --agent-input-max-width: min(92vw, 560px);
  }

  .mode-button span {
    display: none;
  }

  .welcome-icon {
    width: 76px;
    margin-bottom: var(--space-10);
  }
}
</style>
