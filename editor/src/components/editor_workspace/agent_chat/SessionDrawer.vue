<!--
  Agent session drawer.

  Usage:
  Slides out from the left side of the Agent panel and manages backend chat
  sessions for the current editor user_id.
-->
<script setup lang="ts">
import { History, MessageSquarePlus, PanelLeft, Plus, Trash2, X } from 'lucide-vue-next'

import { useSessionStore } from '@/stores/session'
import type { SessionRecord } from '@/api/session'

const props = defineProps<{
  open: boolean
  userId: string
  mode?: 'panel' | 'page'
  chatModeLabel?: string
}>()

const emit = defineEmits<{
  close: []
  create: []
  select: [sessionId: string]
  'toggle-chat-mode': []
}>()

const sessionStore = useSessionStore()

function displayName(session: SessionRecord) {
  return session.session_name || session.session_id.slice(0, 8)
}

function selectSession(sessionId: string) {
  emit('select', sessionId)
  if (props.mode !== 'page') {
    emit('close')
  }
}

async function deleteSession(sessionId: string, event: MouseEvent) {
  event.stopPropagation()
  await sessionStore.remove(sessionId)
}

async function clearAllSessions() {
  if (!sessionStore.sessions.length) {
    return
  }
  if (!window.confirm('确认清空全部会话？此操作不可撤销。')) {
    return
  }
  await sessionStore.clearAll(props.userId)
}
</script>

<template>
  <aside class="session-drawer" :class="{ open, 'page-mode': mode === 'page' }">
    <div class="drawer-titlebar">
      <template v-if="mode === 'page'">
        <div class="brand-copy">
          <strong>MetaWeave</strong>
        </div>
      </template>
      <div v-else class="traffic-lights">
        <span class="traffic-dot red"></span>
        <span class="traffic-dot yellow"></span>
        <span class="traffic-dot green"></span>
      </div>
      <span v-if="mode !== 'page'" class="window-filename">sessions --list</span>
      <button class="close-button" type="button" :title="mode === 'page' ? '收起侧边栏' : 'Close sessions'" @click="emit('close')">
        <PanelLeft v-if="mode === 'page'" :size="15" />
        <X v-else :size="13" />
      </button>
    </div>

    <div class="drawer-toolbar">
      <div class="primary-actions">
        <button class="new-btn" type="button" @click="emit('create')">
          <MessageSquarePlus v-if="mode === 'page'" :size="15" />
          <Plus v-else :size="12" />
          <span>New Chat</span>
        </button>
        <button
          v-if="mode === 'page'"
          class="mode-btn"
          type="button"
          :title="`切换对话模式: 当前 ${chatModeLabel || 'chat'}`"
          @click="emit('toggle-chat-mode')"
        >
          <History :size="15" />
        </button>
      </div>
    </div>

    <!-- history label removed per request -->

    <div class="session-list">
      <button
        v-for="session in sessionStore.sessions"
        :key="session.session_id"
        class="session-item"
        :class="{ active: session.session_id === sessionStore.currentSessionId }"
        type="button"
        @click="selectSession(session.session_id)"
      >
        <span class="session-icon">$</span>
        <span class="session-name">{{ displayName(session) }}</span>
        <span class="session-time">{{ session.updated_at?.slice(0, 10) }}</span>
        <span class="delete-btn" title="删除会话" @click="deleteSession(session.session_id, $event)">
          <X :size="12" />
        </span>
      </button>
      <p v-if="!sessionStore.sessions.length" class="empty-hint">$ no sessions found</p>
    </div>

    <div v-if="mode === 'page' || sessionStore.sessions.length > 0" class="drawer-footer">
      <button v-if="sessionStore.sessions.length > 0" class="clear-all-btn" type="button" @click="clearAllSessions">
        <Trash2 :size="12" />
        <span>Clear All Sessions</span>
      </button>
      <div v-if="mode === 'page'" class="user-strip">
        <span class="user-dot"></span>
        <div>
          <span class="user-label">User</span>
          <strong>{{ userId || 'not signed in' }}</strong>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.session-drawer {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 12px;
  z-index: 4;
  display: flex;
  flex-direction: column;
  width: min(290px, calc(100% - 24px));
  overflow: hidden;
  border: 1px solid var(--color-border);
  background: var(--color-bg-elevated);
  transform: translateX(calc(-100% - 16px));
  transition:
    transform 200ms ease,
    opacity 160ms ease;
  opacity: 0;
}

.session-drawer.open {
  transform: translateX(0);
  opacity: 1;
}

.session-drawer.page-mode {
  --drawer-page-border: rgba(255, 255, 255, 0.10);
  --drawer-page-bg-top: rgba(15, 18, 31, 0.94);
  --drawer-page-bg-bottom: rgba(12, 14, 24, 0.90);
  --drawer-page-bg-solid: rgba(13, 17, 28, 0.86);
  --drawer-page-hover: rgba(255, 255, 255, 0.08);
  --drawer-page-active: rgba(255, 255, 255, 0.08);
  top: 0;
  bottom: 0;
  left: 0;
  width: 280px;
  max-width: min(280px, 80vw);
  border: 0;
  border-right: 1px solid var(--drawer-page-border);
  background:
    linear-gradient(180deg, var(--drawer-page-bg-top), var(--drawer-page-bg-bottom)),
    var(--drawer-page-bg-solid);
  box-shadow: none;
  backdrop-filter: blur(18px);
  transform: translateX(calc(-100% + 10px));
}

:root[data-theme="light"] .session-drawer.page-mode {
  --drawer-page-border: rgba(66, 36, 235, 0.12);
  --drawer-page-bg-top: rgba(255, 255, 255, 0.94);
  --drawer-page-bg-bottom: rgba(244, 246, 255, 0.92);
  --drawer-page-bg-solid: rgba(255, 255, 255, 0.88);
  --drawer-page-hover: rgba(66, 36, 235, 0.08);
  --drawer-page-active: rgba(66, 36, 235, 0.10);
}

.session-drawer.page-mode.open {
  transform: translateX(0);
}

.drawer-titlebar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 34px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-muted);
}

.page-mode .drawer-titlebar {
  grid-template-columns: minmax(0, 1fr) auto;
  min-height: 58px;
  padding: 0 var(--space-20);
  border-bottom: 0;
  background: transparent;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-copy strong {
  overflow: hidden;
  color: var(--color-text-primary);
  font-family: "Monocraft", var(--font-code);
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.traffic-lights {
  display: flex;
  gap: 5px;
}

.traffic-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.traffic-dot.red { background: #ff5f57; }
.traffic-dot.yellow { background: #ffbd2e; }
.traffic-dot.green { background: #28c840; }

.window-filename {
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 0;
  background: transparent;
  color: var(--color-text-tertiary);
}

.page-mode .close-button {
  width: 30px;
  height: 30px;
  border-radius: 999px;
}

.page-mode .close-button:hover {
  background: var(--drawer-page-hover);
  color: var(--color-text-primary);
}

.drawer-toolbar,
.drawer-footer {
  padding: var(--space-8) var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.drawer-footer {
  border-top: 1px solid var(--color-border);
  border-bottom: 0;
}

.page-mode .drawer-toolbar {
  padding: 0 0 var(--space-14);
  border-bottom: 0;
}

.page-mode .drawer-footer {
  display: grid;
  gap: var(--space-10);
  padding: var(--space-12);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.new-btn,
.clear-all-btn,
.mode-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.primary-actions {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.page-mode .primary-actions {
  margin: 0 var(--space-20);
}

.page-mode .new-btn {
  justify-content: center;
  flex: 0 1 auto;
  min-height: 36px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 600;
}

.page-mode .mode-btn {
  justify-content: center;
  width: 36px;
  min-width: 36px;
  min-height: 36px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
}

.page-mode .clear-all-btn {
  min-height: 34px;
  border-color: transparent;
  border-radius: 999px;
  background: transparent;
}

.new-btn:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
}

.clear-all-btn:hover {
  border-color: rgba(197, 101, 101, 0.4);
  background: rgba(197, 101, 101, 0.08);
  color: #c56565;
}

.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.page-mode .session-list {
  padding: var(--space-12) var(--space-12) var(--space-8);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-8) var(--space-12);
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  text-align: left;
}

.page-mode .session-item {
  min-height: 30px;
  margin-bottom: var(--space-2);
  padding: 0 var(--space-8);
  border-left: 0;
  border-radius: 6px;
  font-family: var(--font-ui);
  font-size: 12px;
}

.session-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.session-item.active {
  background: var(--color-accent-muted);
  color: var(--color-accent);
}

.page-mode .session-item.active {
  background: var(--drawer-page-active);
  color: var(--color-text-primary);
}

.session-icon,
.session-time {
  flex-shrink: 0;
  color: var(--color-text-tertiary);
}

.session-time {
  font-size: 9px;
}

.session-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  opacity: 0;
  color: var(--color-text-tertiary);
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(197, 101, 101, 0.12);
  color: #c56565;
}

.empty-hint {
  padding: var(--space-20);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  text-align: center;
}

.user-strip {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
  padding: var(--space-8) var(--space-10);
  border-radius: 999px;
  color: var(--color-text-secondary);
}

.user-dot {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
}

.user-strip div {
  min-width: 0;
}

.user-label {
  display: block;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 9px;
}

.user-strip strong {
  display: block;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
