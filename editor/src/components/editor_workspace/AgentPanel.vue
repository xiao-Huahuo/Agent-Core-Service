<!--
  Right-side Agent panel.

  Usage:
  Hosts the editor Agent chat. It reuses the console chat/session backend and
  keeps observability and settings outside of the editor side panel.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import darkTitle from '@/assets/images/暗色标题.png'
import lightTitle from '@/assets/images/亮色标题.png'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import ChatInput from '@/components/editor_workspace/agent_chat/ChatInput.vue'
import LoaderCube from '@/components/editor_workspace/agent_chat/LoaderCube.vue'
import MessageList from '@/components/editor_workspace/agent_chat/MessageList.vue'
import SessionDrawer from '@/components/editor_workspace/agent_chat/SessionDrawer.vue'
import StreamingIndicator from '@/components/editor_workspace/agent_chat/StreamingIndicator.vue'
import TaskListDrawer from '@/components/editor_workspace/agent_chat/TaskListDrawer.vue'
import ChildAgentPanel from '@/components/editor_workspace/agent_chat/ChildAgentPanel.vue'
import EnvironmentChangeCard from '@/components/editor_workspace/agent_chat/EnvironmentChangeCard.vue'
import ChangeDetailDrawer from '@/components/editor_workspace/agent_chat/ChangeDetailDrawer.vue'
import { useChatStore, useSessionChatStore } from '@/stores/chat'
import type { AgentUploadedAttachment } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useSkillsStore } from '@/stores/skills'
import { useFavoritesStore } from '@/stores/favorites'
import { useTaskListStore } from '@/stores/taskList'
import { useWorkspaceStore } from '@/stores/workspace'
import type { AgentAccessMode, AgentLoopMode } from '@/api/agent'
import type { SessionRecord } from '@/api/session'
import { uploadAgentAttachment } from '@/api/agent'
import { fetchLLMConfig, fetchSensitiveWords, saveSensitiveWords } from '@/api/settings'
import type { AgentChangeSnapshot } from '@/api/agentChanges'

type MessageListApi = {
  scrollToBottom: (options?: ScrollToOptions) => void
}

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const skillsStore = useSkillsStore()
const favoritesStore = useFavoritesStore()
const taskListStore = useTaskListStore()
const workspaceStore = useWorkspaceStore()
const props = withDefaults(defineProps<{
  mode?: 'panel' | 'page'
  /** 在嵌入式场景中打开指定的持久化任务会话。 */
  sessionId?: string
  /** Silently follow messages persisted by an external queue worker. */
  liveSync?: boolean
}>(), {
  mode: 'panel',
  sessionId: '',
  liveSync: false,
})
// Queue dialogs mount a complete Agent panel for a fixed task session.  Give
// it its own stream state so opening it cannot replace or cancel the page chat.
const chatStore = shallowRef(props.sessionId ? useSessionChatStore(props.sessionId) : useChatStore())
const emit = defineEmits<{
  expand: []
}>()
const sessionDrawerOpen = ref(false)
// 融合侧边栏(任务列表 + 子 Agent)统一开关
const agentSidebarOpen = ref(false)
// 两张卡片独立可见:各自可叉掉,不影响另一张;仅剩一张时再叉掉则收起整个侧边栏
const taskListCardOpen = ref(false)
const childAgentCardOpen = ref(false)
const environmentCardOpen = ref(false)
const changeDetailOpen = ref(false)
const selectedChangeSnapshot = ref<AgentChangeSnapshot | null>(null)
const isBootstrapping = ref(false)
const referenceText = ref('')
const messageListRef = ref<MessageListApi | null>(null)
const isMessageListAtBottom = ref(true)
const sessionLoading = ref(false)
let taskHistoryPollTimer: number | null = null
const loadingSessionId = ref('')
const contextWindowTokens = ref(128000)
const safetyDisabled = ref(false)
const safetyLoading = ref(false)
const dragDepth = ref(0)
const isUploadingAttachment = ref(false)
const uploadStatusText = ref('')
const modeSwitchRef = ref<HTMLElement | null>(null)
const loopModeMenuOpen = ref(false)
const skillMenuOpen = ref(false)
const modeIndicatorStyle = computed(() => {
  if (settingsStore.chatMode === 'tool') {
    return { width: 'calc(50% - 2px)', transform: 'translateX(0)' }
  }
  return { width: 'calc(50% - 2px)', transform: 'translateX(100%) translateX(2px)' }
})

const userId = computed(() => settingsStore.profile.userId)
const activeSessionId = computed(() => props.sessionId || sessionStore.currentSessionId)
/** Switches only this panel's chat state; existing session streams keep running. */
function useActiveSessionChat(sessionId: string) {
  if (!props.sessionId && sessionId) chatStore.value = useSessionChatStore(sessionId)
}
const isDark = computed(() => settingsStore.isDark)
const welcomeTitleSrc = computed(() => isDark.value ? darkTitle : lightTitle)
const logoSrc = computed(() => isDark.value ? darkLogo : lightLogo)
const hasMessages = computed(() => chatStore.value.messages.filter((m) => m.role !== 'system').length > 0)
const hasStreamingContent = computed(() => !!chatStore.value.lastMessage?.content)
// 与 ChatInput 的 .task-suggestions 显示条件一致:非居中(有消息)、无附件、有建议
const hasSuggestionOverlay = computed(() => {
  if (chatStore.value.taskSuggestions.length === 0) return false
  if (!hasMessages.value && !chatStore.value.isStreaming) return false
  if (chatStore.value.pendingAttachments.length > 0) return false
  return true
})
const isAttachmentDropActive = computed(() => dragDepth.value > 0 || isUploadingAttachment.value)

/** Start or stop silent history synchronization for an externally-run task. */
function syncTaskHistoryPolling(enabled: boolean) {
  if (taskHistoryPollTimer !== null) {
    window.clearInterval(taskHistoryPollTimer)
    taskHistoryPollTimer = null
  }
  if (!enabled || !props.sessionId) return
  taskHistoryPollTimer = window.setInterval(() => {
    if (userId.value) void chatStore.value.syncHistory(props.sessionId!, userId.value)
  }, 1500)
}
const sessionTitle = computed(() => {
  const name = sessionStore.sessions.find((session) => session.session_id === activeSessionId.value)?.session_name || 'new session'
  return name.replace(/^标题:/, '').trim()
})
/** Visible even with the history drawer collapsed, so parallel runs are never hidden. */
const runningSessions = computed(() => sessionStore.streamingSessionIds
  .map((sessionId) => sessionStore.sessions.find((session) => session.session_id === sessionId))
  .filter((session): session is SessionRecord => Boolean(session)))
function runningSessionName(session: SessionRecord) {
  return (session.session_name || session.session_id.slice(0, 8)).replace(/^标题:/, '').trim()
}
const chatModeLabel = computed(() => settingsStore.chatMode === 'chat' ? 'chat' : 'tool')
const currentLargeModelName = ref('')
const sessionSources = computed(() => {
  const unique = new Map<string, import('@/stores/chat').SourceItem>()
  for (const message of chatStore.value.messages) {
    const citationMap = message.metadata?.citation_map
    if (!citationMap || typeof citationMap !== 'object' || Array.isArray(citationMap)) continue
    for (const source of Object.values(citationMap)) {
      if (!source || typeof source !== 'object' || Array.isArray(source)) continue
      const record = source as Record<string, unknown>
      const uri = typeof record.source_uri === 'string' ? record.source_uri : ''
      if (!uri || unique.has(uri)) continue
      unique.set(uri, {
        source_uri: uri,
        content: typeof record.content === 'string' ? record.content : '',
        source: typeof record.source === 'string' ? record.source : undefined,
        title: typeof record.title === 'string' ? record.title : undefined,
      })
    }
  }
  return [...unique.values()]
})
const modelConfigLabel = computed(() => currentLargeModelName.value || '配置模型')
const loopModeOptions: Array<{ value: AgentLoopMode; label: string }> = [
  { value: 'auto', label: 'Auto' },
  { value: 'simple', label: 'Simple' },
  { value: 'react', label: 'ReAct' },
  { value: 'plan', label: 'Plan' },
]
const selectedLoopModeLabel = computed(() => {
  return loopModeOptions.find((option) => option.value === settingsStore.agentLoopMode)?.label || 'Auto'
})
const extractedSkills = computed(() => {
  return [...skillsStore.skills].sort((a, b) => a.name.localeCompare(b.name))
})
const knowledgeTitle = computed(() => {
  const name = settingsStore.activeKnowledgeLibrary?.name?.trim()
  if (name) return name
  const parts = settingsStore.profile.knowledgeDir.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] || '未命名'
})

async function reloadSessions() {
  if (!userId.value) {
    sessionStore.clearSelection()
    chatStore.value.clear()
    return
  }
  isBootstrapping.value = true
  try {
    await sessionStore.load(userId.value)
    if (activeSessionId.value) {
      await loadSelectedSessionHistory(activeSessionId.value)
    }
  } finally {
    isBootstrapping.value = false
  }
}

async function createSession() {
  if (!userId.value) {
    return
  }
  // 当前对话没有任何消息时不创建新对话，只收起侧边栏
  if (!chatStore.value.messages.some((m) => m.role !== 'system')) {
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
  // A queue detail is pinned to its task thread.  Navigating its session list
  // must not replace the task conversation currently being inspected.
  if (props.sessionId) return
  sessionStore.select(sessionId)
  useActiveSessionChat(sessionId)
  await loadSelectedSessionHistory(sessionId)
}

async function loadSelectedSessionHistory(sessionId: string, force = false) {
  if (!userId.value || loadingSessionId.value === sessionId || (!force && chatStore.value.loadedSessionId === sessionId)) {
    return
  }
  loadingSessionId.value = sessionId
  sessionLoading.value = true
  try {
    await chatStore.value.loadHistory(sessionId, userId.value)
  } finally {
    sessionLoading.value = false
    loadingSessionId.value = ''
  }
}

async function sendMessage(text: string, reference = '') {
  if (!userId.value) {
    return
  }
  // Bind a durable thread before starting the stream.  The previous thread
  // can then keep streaming in its own store while this one begins.
  if (!activeSessionId.value) {
    const sessionId = await sessionStore.create(userId.value)
    useActiveSessionChat(sessionId)
  }
  await chatStore.value.send(
    userId.value,
    activeSessionId.value,
    text,
    reference,
    settingsStore.agentLoopMode,
    settingsStore.agentAccessMode,
  )
}

async function createTaskListFromInput(title: string, items: string[]) {
  if (!userId.value || items.length === 0) {
    return
  }
  let targetSessionId = activeSessionId.value
  if (!targetSessionId) {
    targetSessionId = await sessionStore.create(userId.value)
    if (!props.sessionId) sessionStore.select(targetSessionId)
  }
  const taskList = await taskListStore.create(targetSessionId, title || 'Task list', items, { open: props.mode === 'page' })
  if (!taskList) {
    return
  }
  const promptLines = [
    `Task list: ${taskList.title}`,
    ...taskList.items.map((item, index) => `${index + 1}. ${item.title}`),
    '',
    'Please work through this task list. Use complete_task_list_item after each completed item and finish_task_list when the list is done.',
  ]
  await sendMessage(promptLines.join('\n'))
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

/** Exposes the persisted Agent loop mode to the shared radio menu. */
const agentLoopModeModel = computed<AgentLoopMode>({
  get: () => settingsStore.agentLoopMode,
  set: setAgentLoopMode,
})

async function refreshSkills() {
  await skillsStore.loadSkills()
}

function selectSkillReference(skillName: string) {
  referenceText.value = `用户要求使用Skill： ${skillName}`
  skillMenuOpen.value = false
}

function setAgentAccessMode(mode: AgentAccessMode) {
  settingsStore.setAgentAccessMode(mode)
}

function setChatRenderMode(mode: 'chat' | 'tool') {
  if (settingsStore.chatMode !== mode) {
    settingsStore.toggleChatMode()
  }
}

async function loadCurrentModelConfig() {
  if (!userId.value) {
    currentLargeModelName.value = ''
    return
  }
  try {
    const config = await fetchLLMConfig(userId.value)
    currentLargeModelName.value = config.model_name?.trim() || ''
    contextWindowTokens.value = config.context_window_tokens ?? 128000
  } catch {
    currentLargeModelName.value = ''
  }
}

function openModelSettings() {
  localStorage.setItem('agent_editor_settings_active_tab', 'llm')
  window.dispatchEvent(new CustomEvent('agent-settings-tab', { detail: 'llm' }))
  workspaceStore.setMainView('settings')
}

function handleModelConfigUpdated(event: Event) {
  const modelName = (event as CustomEvent<{ modelName?: string }>).detail?.modelName
  currentLargeModelName.value = modelName?.trim() || ''
}

async function loadSafetyState() {
  try {
    const raw = await fetchSensitiveWords()
    const r = raw as Record<string, unknown>
    safetyDisabled.value = r._safety_disabled === true
  } catch { /* 忽略 */ }
}

async function toggleSafety() {
  if (safetyLoading.value) return
  safetyLoading.value = true
  try {
    const raw = await fetchSensitiveWords()
    const r = raw as Record<string, unknown>
    const next = !(r._safety_disabled === true)
    r._safety_disabled = next
    await saveSensitiveWords(r)
    safetyDisabled.value = next
  } catch { /* 忽略 */ }
  finally { safetyLoading.value = false }
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
  void chatStore.value.deleteAttachment(attachment)
}

function sendSuggestion(suggestion: string) {
  void sendMessage(suggestion)
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
  let targetSessionId = activeSessionId.value
  if (!targetSessionId) {
    targetSessionId = await sessionStore.create(userId.value)
    if (!props.sessionId) sessionStore.select(targetSessionId)
  }
  await uploadFiles(files, targetSessionId)
}

async function handleFileSelect(file: File) {
  if (!userId.value) return
  let targetSessionId = activeSessionId.value
  if (!targetSessionId) {
    targetSessionId = await sessionStore.create(userId.value)
    if (!props.sessionId) sessionStore.select(targetSessionId)
  }
  await uploadFiles([file], targetSessionId)
}

async function uploadFiles(files: File[], sessionId: string) {
  isUploadingAttachment.value = true
  try {
    for (const [index, file] of files.entries()) {
      uploadStatusText.value = `Uploading ${index + 1}/${files.length}: ${file.name}`
      const response = await uploadAgentAttachment(userId.value!, sessionId, file)
      chatStore.value.addPendingAttachment(response.attachment)
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

watch(userId, () => {
  void reloadSessions().then(() => {
    if (!props.sessionId) return
    void selectSession(props.sessionId)
  })
  if (userId.value) {
    void favoritesStore.load(userId.value, 'session', '')
  }
  void loadCurrentModelConfig()
})

watch(
  () => props.mode,
  (mode) => {
    taskListStore.setAutoOpenOnUpdate(mode === 'page')
  },
  { immediate: true },
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

watch(
  () => chatStore.value.isStreaming,
  (streaming, wasStreaming) => {
    if (streaming || !wasStreaming || !userId.value || !activeSessionId.value) {
      return
    }
    window.setTimeout(() => {
      if (!userId.value || !activeSessionId.value || chatStore.value.isStreaming) {
        return
      }
      void chatStore.value.refreshTaskSuggestions(userId.value, activeSessionId.value)
    }, 0)
  },
)

// 顶栏按钮召唤任务列表卡片:可见时收起(与卡片 X 逻辑一致,仅剩它则收整个侧边栏),不可见时打开
function toggleTaskListCard() {
  if (taskListCardOpen.value) {
    closeTaskListCard()
  } else {
    taskListCardOpen.value = true
    agentSidebarOpen.value = true
  }
}

// 顶栏按钮召唤子 Agent 卡片:同上
function toggleChildAgentCard() {
  if (childAgentCardOpen.value) {
    closeChildAgentCard()
  } else {
    childAgentCardOpen.value = true
    agentSidebarOpen.value = true
  }
}

function toggleEnvironmentCard() {
  environmentCardOpen.value = !environmentCardOpen.value
  if (environmentCardOpen.value) {
    agentSidebarOpen.value = true
  } else {
    changeDetailOpen.value = false
    if (!taskListCardOpen.value && !childAgentCardOpen.value) agentSidebarOpen.value = false
  }
}

function closeEnvironmentCard() {
  environmentCardOpen.value = false
  changeDetailOpen.value = false
  if (!taskListCardOpen.value && !childAgentCardOpen.value) agentSidebarOpen.value = false
}

function showChangeDetails(snapshot: AgentChangeSnapshot) {
  selectedChangeSnapshot.value = snapshot
  changeDetailOpen.value = true
}

// 叉掉任务列表卡片:若另一张(子 Agent)卡片也不可见则一并收起整个侧边栏
function closeTaskListCard() {
  taskListCardOpen.value = false
  if (!childAgentCardOpen.value) {
    agentSidebarOpen.value = false
  }
}

// 叉掉子 Agent 卡片:若另一张(任务列表)卡片也不可见则一并收起整个侧边栏
function closeChildAgentCard() {
  childAgentCardOpen.value = false
  if (!taskListCardOpen.value) {
    agentSidebarOpen.value = false
  }
}

// 任务列表创建/更新自动打开时,联动展开融合侧边栏
watch(() => taskListStore.sidebarOpen, (open) => {
  if (open) {
    taskListCardOpen.value = true
    agentSidebarOpen.value = true
  }
})

// 子 Agent 事件由流消息写入 ChatStore；出现时展示对应卡片而非空侧栏。
watch(
  () => chatStore.value.messages.length,
  () => {
    if (chatStore.value.isStreaming && chatStore.value.messages[chatStore.value.messages.length - 1]?.node === 'child_agent') {
      childAgentCardOpen.value = true
      agentSidebarOpen.value = true
    }
  },
)

function syncChildAgentWatcher() {
  const sessionId = activeSessionId.value
  if (userId.value && sessionId) {
    chatStore.value.startChildAgentWatcher(userId.value, sessionId)
  } else {
    chatStore.value.stopChildAgentWatcher()
  }
}

watch([userId, activeSessionId], syncChildAgentWatcher)

watch(
  activeSessionId,
  (sessionId) => {
    // The first send creates and selects its session after inserting the local
    // user message. Reloading the still-empty history here would clear it.
    if (sessionId && !chatStore.value.isStreaming) {
      void loadSelectedSessionHistory(sessionId)
    }
  },
)

onMounted(() => {
  window.addEventListener('agent-model-config-updated', handleModelConfigUpdated as EventListener)
  window.addEventListener('agent-change-updated', handleChangeUpdated as EventListener)
  void reloadSessions().then(() => {
    if (props.sessionId) void loadSelectedSessionHistory(props.sessionId)
  })
  if (userId.value) {
    void favoritesStore.load(userId.value, 'session', '')
  }
  void loadCurrentModelConfig()
  void refreshSkills()
  void loadSafetyState()
  void settingsStore.fetchWebSearchSettings()
  syncChildAgentWatcher()
  syncTaskHistoryPolling(props.liveSync)
})

/** 嵌入式任务查看器切换到另一任务时，同步加载对应的完整 Agent 会话。 */
watch(() => props.sessionId, (sessionId) => {
  if (sessionId) void loadSelectedSessionHistory(sessionId)
})

watch(() => props.liveSync, syncTaskHistoryPolling)

onBeforeUnmount(() => {
  window.removeEventListener('agent-model-config-updated', handleModelConfigUpdated as EventListener)
  window.removeEventListener('agent-change-updated', handleChangeUpdated as EventListener)
  taskListStore.setAutoOpenOnUpdate(true)
  chatStore.value.stopChildAgentWatcher()
  if (taskHistoryPollTimer !== null) {
    window.clearInterval(taskHistoryPollTimer)
    taskHistoryPollTimer = null
  }
})

/** Keeps an open detail drawer in sync with a just-completed file patch. */
function handleChangeUpdated(event: CustomEvent<AgentChangeSnapshot>) {
  const snapshot = event.detail
  if (changeDetailOpen.value && snapshot?.session_id === activeSessionId.value) {
    selectedChangeSnapshot.value = snapshot
  }
}
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
        <IcIcon name="cloud-upload" :size="38" />
        <span>{{ uploadStatusText || 'Drop files to attach to this session' }}</span>
      </div>
    </Transition>

    <SessionDrawer
      :open="sessionDrawerOpen"
      :mode="props.mode"
      :user-id="userId"
      :selected-session-id="activeSessionId"
      :streaming-session-ids="sessionStore.streamingSessionIds"
      @close="closeSessionDrawer"
      @create="createSession"
      @select="selectSession"
    />

    <div class="agent-chat-card">
    <header v-if="props.mode === 'page'" class="agent-topbar">
      <div class="topbar-capsule" :class="{ 'drawer-open': sessionDrawerOpen }">
        <button class="capsule-logo-btn" type="button" title="Toggle sidebar" @click="sessionDrawerOpen = !sessionDrawerOpen">
          <img :src="logoSrc" class="capsule-logo" alt="MetaWeave" />
        </button>
        <span class="capsule-divider" data-divider></span>
        <div ref="modeSwitchRef" class="capsule-switch" role="group" aria-label="Chat render mode">
          <span class="mode-indicator" :style="modeIndicatorStyle"></span>
          <button
            class="capsule-switch-btn"
            :class="{ active: settingsStore.chatMode === 'tool' }"
            type="button"
            aria-label="Tool mode"
            :aria-pressed="settingsStore.chatMode === 'tool'"
            @click="setChatRenderMode('tool')"
          >
            Tool
          </button>
          <button
            class="capsule-switch-btn"
            :class="{ active: settingsStore.chatMode === 'chat' }"
            type="button"
            aria-label="Chat mode"
            :aria-pressed="settingsStore.chatMode === 'chat'"
            @click="setChatRenderMode('chat')"
          >
            Chat
          </button>
        </div>
      </div>
      <button
        class="capsule-safety-btn"
        :class="{ disabled: safetyDisabled }"
        type="button"
        :title="safetyDisabled ? '安全审核已关闭' : '安全审核已开启'"
        :disabled="safetyLoading"
        @click="toggleSafety"
      >
        <span v-if="safetyLoading" class="capsule-safety-dot loading"></span>
        <span v-else class="capsule-safety-dot" :class="safetyDisabled ? '' : 'on'"></span>
        <span class="capsule-safety-label">审核</span>
      </button>
      <span class="topbar-title">{{ sessionTitle }}</span>
      <div class="topbar-right">
        <button class="topbar-tool-button" type="button" title="环境与变更" aria-label="环境与变更" :aria-pressed="environmentCardOpen" @click="toggleEnvironmentCard">
          <IcIcon name="dns" :size="17" />
        </button>
        <button
          class="topbar-tool-button"
          type="button"
          title="任务列表"
          :aria-pressed="taskListCardOpen"
          @click="toggleTaskListCard"
        >
          <IcIcon name="checklist" :size="17" />
        </button>
        <button
          class="topbar-tool-button"
          type="button"
          title="子 Agent"
          :aria-pressed="childAgentCardOpen"
          @click="toggleChildAgentCard"
        >
          <IcIcon name="group" :size="17" />
        </button>
        <DropdownMenu v-model:open="skillMenuOpen">
          <DropdownMenuTrigger as-child>
            <button class="topbar-skill-trigger" type="button" title="Skill" aria-label="Skill" :disabled="!userId">
              <span>Skill</span>
              <IcIcon name="chevron-down" :size="12" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuPortal>
            <DropdownMenuContent align="end">
              <div class="topbar-skill-menu-head">
                <DropdownMenuLabel>Skills</DropdownMenuLabel>
                <button
                  class="topbar-skill-refresh"
                  type="button"
                  title="刷新 Skill"
                  :disabled="skillsStore.loading"
                  @click.stop="refreshSkills"
                >
                  <IcIcon name="refresh" :size="13" :class="{ spinning: skillsStore.loading }" />
                </button>
              </div>
              <div class="topbar-skill-list">
                <DropdownMenuItem
                  v-for="skill in extractedSkills"
                  :key="skill.skill_id"
                  class="topbar-skill-option"
                  @select="selectSkillReference(skill.name)"
                >
                  <span class="topbar-skill-name">{{ skill.name }}</span>
                </DropdownMenuItem>
                <div v-if="extractedSkills.length === 0" class="topbar-skill-empty">
                  {{ skillsStore.loading ? '正在读取' : '暂无 Skill' }}
                </div>
              </div>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenu>
        <DropdownMenu v-model:open="loopModeMenuOpen">
          <DropdownMenuTrigger as-child>
            <button class="topbar-loop-mode-trigger" type="button" title="Agent Loop 模式" aria-label="Agent Loop 模式" :disabled="!userId">
              <span>{{ selectedLoopModeLabel }}</span>
              <IcIcon name="chevron-down" :size="12" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuPortal>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>思考模式</DropdownMenuLabel>
              <DropdownMenuRadioGroup v-model="agentLoopModeModel">
                <DropdownMenuRadioItem v-for="option in loopModeOptions" :key="option.value" :value="option.value">
                  <span class="topbar-loop-mode-copy">
                    <strong>{{ option.label }}</strong>
                  </span>
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenu>
        <button class="panel-new-session" type="button" title="新对话" @click="createSession">
          <IcIcon name="add" :size="17" />
          <span>新对话</span>
        </button>
      </div>
    </header>

    <div class="agent-body">
      <header v-if="props.mode === 'panel'" class="agent-titlebar">
      <button
        class="icon-button drawer-toggle"
        type="button"
        title="Open sessions"
        @click="sessionDrawerOpen = !sessionDrawerOpen"
      >
        <IcIcon name="forum" :size="16" />
      </button>
       <div class="title-meta">
         <strong>{{ sessionTitle }}</strong>
       </div>
      <div class="title-actions">
        <button class="icon-button" type="button" title="环境与变更" :aria-pressed="environmentCardOpen" @click="toggleEnvironmentCard"><IcIcon name="dns" :size="16" /></button>
        <button
          class="icon-button"
          type="button"
          title="任务列表"
          :aria-pressed="taskListCardOpen"
          @click="toggleTaskListCard"
        >
          <IcIcon name="checklist" :size="16" />
        </button>
        <button
          class="icon-button"
          type="button"
          title="子 Agent"
          :aria-pressed="childAgentCardOpen"
          @click="toggleChildAgentCard"
        >
          <IcIcon name="group" :size="16" />
        </button>
        <button
          v-if="props.mode === 'panel'"
          class="icon-button"
          type="button"
          title="Expand Agent page"
          @click="emit('expand')"
        >
          <IcIcon name="open-in-full" :size="16" />
        </button>
        <button class="panel-new-session" type="button" title="新对话" @click="createSession">
          <IcIcon name="add" :size="17" />
          <span>新对话</span>
        </button>
        <button class="mode-button" type="button" title="Toggle chat render mode" @click="settingsStore.toggleChatMode">
          <IcIcon name="history" :size="15" />
          <span>{{ chatModeLabel }}</span>
        </button>
      </div>
    </header>

    <div class="agent-content-row">
    <main class="chat-body" :class="{ dimmed: isBootstrapping }">
      <Transition name="welcome-fade">
        <div v-if="!hasMessages && !chatStore.isStreaming && !sessionLoading" class="welcome-center">
          <img :src="logoSrc" class="welcome-cap-icon" alt="" />
          <img :src="welcomeTitleSrc" class="welcome-logo" alt="MetaWeave" />
          <p class="welcome-subtitle">在知识库 {{ knowledgeTitle }} 中有什么问题?</p>
        </div>
      </Transition>
      <div v-if="sessionLoading" class="history-loading">
        <LoaderCube />
        <span>加载会话历史...</span>
      </div>
      <div v-else class="chat-content">
      <MessageList
        ref="messageListRef"
        :messages="chatStore.messages"
        :is-streaming="chatStore.isStreaming"
        :merge-assistants="settingsStore.chatMode === 'chat'"
        :suggestion-overlay="hasSuggestionOverlay"
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
        <svg class="scroll-svg" xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor">
          <path d="M440-800v487L216-537l-56 57 320 320 320-320-56-57-224 224v-487h-80Z"></path>
        </svg>
      </button>
      <div v-if="chatStore.isStreaming" class="thinking-flow" aria-live="polite">
        <span class="thinking-shimmer-text">正在思考</span>
      </div>
      <ChatInput
        :disabled="!userId"
        :centered="!hasMessages && !chatStore.isStreaming"
        :compact="props.mode === 'panel'"
        :web-search-enabled="settingsStore.profile.webSearchEnabled"
        :model-label="modelConfigLabel"
        :agent-access-mode="settingsStore.agentAccessMode"
        :reference="referenceText"
        :attachments="chatStore.pendingAttachments"
        :suggestions="chatStore.taskSuggestions"
        :suggestions-loading="chatStore.suggestionsLoading"
        :messages="chatStore.messages"
        :max-context-tokens="contextWindowTokens"
        :is-streaming="chatStore.isStreaming"
        @send="sendMessage"
        @select-suggestion="sendSuggestion"
        @toggle-web-search="handleToggleWebSearch"
        @configure-model="openModelSettings"
        @set-agent-access-mode="setAgentAccessMode"
        @clear-reference="clearReference"
        @remove-attachment="removeAttachment"
        @file-select="handleFileSelect"
        @cancel-stream="chatStore.cancelStream"
        @create-task-list="createTaskListFromInput"
      />
    </div>
    </main>
    <aside class="agent-sidebar" :class="{ open: agentSidebarOpen }" aria-label="任务与子 Agent 侧边栏">
      <section v-show="environmentCardOpen" class="agent-sidebar-card environment-card-shell">
        <EnvironmentChangeCard
          :session-id="activeSessionId || ''"
          :user-id="userId || ''"
          :sources="sessionSources"
          :running-sessions="runningSessions"
          :active-session-id="activeSessionId || ''"
          @close="closeEnvironmentCard"
          @show-changes="showChangeDetails"
          @select-session="selectSession"
        />
      </section>
      <section v-show="taskListCardOpen" class="agent-sidebar-card task-list-card">
        <TaskListDrawer @close="closeTaskListCard" />
      </section>
      <section v-show="childAgentCardOpen" class="agent-sidebar-card child-agent-card">
        <ChildAgentPanel
          :session-id="sessionStore.currentSessionId || ''"
          @close="closeChildAgentCard"
        />
      </section>
    </aside>
    <ChangeDetailDrawer
      v-if="changeDetailOpen"
      :snapshot="selectedChangeSnapshot"
      @close="changeDetailOpen = false"
    />
    </div>
    </div>
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
  outline: none;
  background: var(--color-chrome-rail-bg);
  height: 100%;
}

.agent-panel.agent-page-mode {
  --agent-drawer-width: 280px;
  --agent-content-offset: 0px;
  --agent-chat-max-width: min(85vw, 1100px);
  --agent-input-max-width: min(75vw, 960px);
  --agent-topbar-height: 48px;
  border: 0;
  overflow: visible;
  background: transparent;
  backdrop-filter: none;
}

.agent-panel.agent-page-mode.agent-drawer-open {
  --agent-content-offset: var(--agent-drawer-width);
  --agent-chat-max-width: min(calc(100vw - var(--agent-content-offset) - 48px), 1100px);
  --agent-input-max-width: min(calc(100vw - var(--agent-content-offset) - 96px), 960px);
}

.agent-chat-card {
  display: contents;
}

.agent-panel.agent-page-mode .agent-chat-card {
  position: relative;
  z-index: 2;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  margin-left: var(--agent-content-offset);
  overflow: hidden;
  border: 0;
  border-radius: 28px;
  background: var(--color-bg-app);
  box-shadow:
    0 10px 15px -3px rgba(0, 0, 0, 0.1),
    0 4px 6px -2px rgba(0, 0, 0, 0.05);
  transition: margin-left 200ms ease;
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
  background: transparent;
}

.agent-titlebar > .drawer-toggle {
  display: none;
}

.agent-titlebar > .title-meta {
  grid-column: 2;
  grid-row: 1;
}

.agent-titlebar > .title-actions {
  display: contents;
}

.agent-titlebar > .title-actions > .icon-button:not(:nth-child(4)),
.agent-titlebar > .title-actions > .mode-button {
  display: none;
}

.agent-titlebar > .title-actions > .icon-button:nth-child(4) {
  grid-column: 1;
  grid-row: 1;
}

.agent-titlebar > .title-actions > .panel-new-session {
  grid-column: 3;
  grid-row: 1;
}

.agent-topbar {
  display: flex;
  align-items: center;
  min-height: var(--agent-topbar-height, 32px);
  padding: 0 var(--space-12);
  gap: var(--space-8);
  background: var(--color-canvas-soft);
  flex-shrink: 0;
  transition: padding-left 200ms ease;
}

.agent-panel.agent-page-mode.agent-drawer-open .agent-topbar {
  padding-left: var(--space-12);
}

.topbar-capsule {
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 3px;
  gap: 0;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  transition: gap 200ms ease, padding 200ms ease;
}

.topbar-capsule.drawer-open {
  gap: 0;
  padding: 3px 10px 3px 6px;
}

.capsule-logo-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: 30px;
  height: 30px;
  padding: 0 var(--space-4);
  flex-shrink: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
  overflow: hidden;
  transition:
    width 200ms ease,
    opacity 160ms ease,
    margin 200ms ease,
    padding 200ms ease;
}

.topbar-capsule.drawer-open .capsule-logo-btn {
  width: 0;
  min-width: 0;
  padding: 0;
  opacity: 0;
  margin: 0;
  pointer-events: none;
}

.capsule-logo {
  display: block;
  height: 18px;
  width: auto;
  object-fit: contain;
}

.capsule-divider {
  width: 1px;
  height: 18px;
  flex-shrink: 0;
  background: var(--color-border);
  transition:
    width 200ms ease,
    opacity 160ms ease;
}

.topbar-capsule.drawer-open [data-divider] {
  width: 0;
  opacity: 0;
}

.capsule-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.capsule-switch-btn {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 28px;
  padding: 0 var(--space-10);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  line-height: 1;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.capsule-switch-btn:hover {
  color: var(--color-text-secondary);
}

.capsule-switch-btn.active {
  color: #ffffff;
}

.topbar-title {
  flex: 1;
  overflow: hidden;
  text-align: center;
  color: var(--color-text-primary);
  font-size: calc(14px * var(--font-scale));
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-4);
}

.topbar-right :deep(.topbar-tool-button),
.topbar-right .topbar-tool-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.topbar-right :deep(.topbar-tool-button:hover:not(:disabled)),
.topbar-right .topbar-tool-button:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
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

/* ---- 安全审核开关 ---- */
.capsule-safety-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: color 150ms;
}

.capsule-safety-btn:hover:not(:disabled) {
  color: var(--color-text-secondary);
}

.capsule-safety-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.capsule-safety-btn.disabled {
  color: var(--color-danger);
}

.capsule-safety-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--color-border);
  flex-shrink: 0;
  transition: background 200ms;
}

.capsule-safety-dot.on {
  background: #22c55e;
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.5);
}

.capsule-safety-dot.loading {
  background: transparent;
  border: 1.5px solid var(--color-text-muted);
  border-top-color: transparent;
  animation: safety-spin 0.6s linear infinite;
}

.capsule-safety-btn.disabled .capsule-safety-dot {
  background: var(--color-danger);
  box-shadow: 0 0 4px rgba(255, 95, 95, 0.4);
}

.capsule-safety-label {
  line-height: 1;
}

@keyframes safety-spin {
  to { transform: rotate(360deg); }
}

.topbar-loop-mode-trigger,
.topbar-skill-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 32px;
  min-width: 78px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.topbar-skill-trigger {
  min-width: 76px;
}

.topbar-loop-mode-trigger:hover,
.topbar-loop-mode-trigger[data-state='open'],
.topbar-skill-trigger:hover,
.topbar-skill-trigger[data-state='open'] {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
}

.topbar-skill-list {
  width: 248px;
  max-height: 340px;
  overflow: auto;
}

.topbar-skill-menu-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 30px;
  padding: var(--space-4) var(--space-6) var(--space-6);
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  text-transform: uppercase;
}

.topbar-skill-refresh {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.topbar-skill-refresh:hover:not(:disabled) {
  background: var(--color-primary-softer);
  color: var(--color-text-primary);
}

.topbar-skill-refresh:disabled {
  cursor: default;
  opacity: 0.55;
}

.topbar-skill-refresh .spinning {
  animation: safety-spin 0.8s linear infinite;
}

.topbar-skill-option {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  min-height: 34px;
  padding: var(--space-6) var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  text-align: left;
}

.topbar-skill-option[data-highlighted] {
  background: var(--color-primary-softer);
  color: var(--color-text-primary);
}

.topbar-skill-name {
  color: inherit;
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
}

.topbar-skill-empty {
  padding: var(--space-10) var(--space-8);
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  text-align: center;
}

.topbar-loop-mode-copy {
  display: grid;
  min-width: 0;
}

.topbar-loop-mode-copy strong {
  font-size: calc(12px * var(--font-scale));
}

.panel-new-session {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  width: auto;
  height: 28px;
  padding: 0 var(--space-10);
  border: 0;
  border-radius: 999px;
  background: var(--color-primary);
  color: #ffffff;
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.panel-new-session:hover {
  border-color: transparent;
  background: var(--color-primary-hover, var(--color-primary));
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

.agent-content-row {
  display: flex;
  flex-direction: row;
  flex: 1;
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
  font-size: calc(13px * var(--font-scale));
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
  font-size: calc(13px * var(--font-scale));
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
  font-size: calc(10px * var(--font-scale));
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
  min-width: 0;
  overflow: hidden;
  transition:
    flex-basis 220ms cubic-bezier(0.4, 0, 0.2, 1),
    opacity var(--transition-fast);
}

/* 融合侧边栏:无边框透明容器,内部纵向排列两张独立圆角阴影卡片,打开时占据宽度挤压对话区 */
.agent-sidebar {
  flex: 0 0 0px;
  display: flex;
  width: min(400px, 38vw);
  min-width: 0;
  flex-direction: column;
  gap: var(--space-10);
  overflow: hidden;
  padding: 0;
  transition: flex-basis 220ms cubic-bezier(0.4, 0, 0.2, 1), padding 220ms cubic-bezier(0.4, 0, 0.2, 1);
}

.agent-sidebar.open {
  flex-basis: min(400px, 38vw);
  overflow: visible;
  padding: var(--space-10);
}

/* 圆角阴影卡片公共样式:用设计系统卡片底色 --color-bg-card(暗色 #111 / 亮色 #fff),
   去边框,四周留白让阴影显形 */
.agent-sidebar-card {
  display: flex;
  min-height: 0;
  flex-direction: column;
  border-radius: var(--radius-xl);
  background: var(--color-bg-card);
  box-shadow:
    0 0 0 4px var(--library-form-ring),
    0 1px 3px rgba(0, 0, 0, 0.1),
    0 4px 12px rgba(0, 0, 0, 0.12);
}

/* 任务列表卡片:按内容弹性展示全部任务(不滚动),任务过多超高时才封顶内部滚动 */
.task-list-card {
  flex: 0 0 auto;
  max-height: min(60vh, 520px);
  overflow: hidden;
}

/* 子 Agent 卡片:按内容弹性适配高度(内容少时收缩不顶到底),超高时被压缩到任务列表以下
   剩余空间内内部滚动。flex-basis auto + grow 0:不拉伸填满剩余;shrink 1 + min-height 0
   允许卡片压缩到可用空间配合内部滚动。顶部始终锚定任务列表底部 */
.child-agent-card {
  flex: 0 1 auto;
  min-height: 0;
  overflow: hidden;
}

.agent-page-mode :deep(.message-list) {
  box-sizing: border-box;
  width: 100%;
  align-self: stretch;
  padding-right: max(var(--space-16), calc((100% - var(--agent-chat-max-width)) / 2));
  padding-left: max(var(--space-16), calc((100% - var(--agent-chat-max-width)) / 2));
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
  left: 50%;
  max-width: var(--agent-input-max-width);
  transition:
    left 200ms ease,
    bottom 350ms cubic-bezier(0.4, 0, 0.2, 1),
    width 350ms cubic-bezier(0.4, 0, 0.2, 1);
}

.agent-page-mode .stream-error {
  width: min(100%, var(--agent-chat-max-width));
  margin-right: max(var(--space-16), calc((100% - var(--agent-chat-max-width)) / 2));
  margin-left: max(var(--space-16), calc((100% - var(--agent-chat-max-width)) / 2));
}

.scroll-bottom-button {
  position: absolute;
  left: 50%;
  bottom: 132px;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  padding: 10px;
  border: 0;
  border-radius: 50%;
  background-color: white;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
  transform: translateX(-50%);
  cursor: pointer;
  transition: all 0.5s;
  color: #0c0c0c;
}

.scroll-bottom-button::after {
  content: "Down";
  position: absolute;
  width: auto;
  background-color: white;
  font-size: calc(12px * var(--font-scale));
  box-sizing: border-box;
  padding: 8px 14px;
  border-radius: 25px;
  top: -44px;
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
  transition: all 0.5s;
  transform: scale(0);
  white-space: nowrap;
  font-family: var(--font-ui);
  font-weight: 600;
  color: #0c0c0c;
}

.scroll-svg {
  transition: all 0.5s;
}

.scroll-bottom-button:hover {
  transform: translateX(-50%) translateY(-3px);
  background-color: #0c0c0c;
  border-color: #0c0c0c;
  color: white;
}

.scroll-bottom-button:hover .scroll-svg {
  fill: white;
  transform: scale(1.2);
}

.scroll-bottom-button:hover::after {
  transform: scale(1);
}

.scroll-bottom-button:active {
  transform: translateX(-50%) translateY(2px);
}

.agent-page-mode .scroll-bottom-button {
  left: 50%;
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
  font-size: calc(13px * var(--font-scale));
  letter-spacing: 0;
}

.agent-page-mode .thinking-flow {
  left: max(var(--space-16), calc((100% - var(--agent-input-max-width)) / 2));
}

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

.agent-page-mode .welcome-center {
  right: auto;
  left: 50%;
  width: min(100%, var(--agent-chat-max-width));
  transform: translateX(-50%);
  transition: right 200ms ease;
}

.welcome-cap-icon {
  display: block;
  width: 120px;
  height: auto;
  object-fit: contain;
  margin-bottom: 8px;
  pointer-events: auto;
  animation: welcome-cap-in 1.2s ease-out forwards;
}

.welcome-logo {
  display: block;
  width: 200px;
  height: auto;
  object-fit: contain;
  pointer-events: auto;
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

.welcome-subtitle {
  margin: var(--space-10) 0 0;
  color: var(--color-text-muted);
  font-size: calc(14px * var(--font-scale));
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
}

.history-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-16);
  flex: 1;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.agent-page-mode .history-loading {
  margin-left: 0;
  width: 100%;
  transition:
    margin-left 200ms ease,
    width 200ms ease;
}

.chat-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
</style>
