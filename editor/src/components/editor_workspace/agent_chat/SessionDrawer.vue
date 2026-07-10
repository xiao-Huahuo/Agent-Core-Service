<!--
  Agent session drawer.

  Usage:
  Slides out from the left side of the Agent panel and manages backend chat
  sessions for the current editor user_id.
-->
<script setup lang="ts">
import { Plus, Trash2, X } from 'lucide-vue-next'

import { useSessionStore } from '@/stores/session'
import type { SessionRecord } from '@/api/session'

const props = defineProps<{
  open: boolean
  userId: string
}>()

const emit = defineEmits<{
  close: []
  create: []
  select: [sessionId: string]
}>()

const sessionStore = useSessionStore()

function displayName(session: SessionRecord) {
  return session.session_name || session.session_id.slice(0, 8)
}

function selectSession(sessionId: string) {
  emit('select', sessionId)
  emit('close')
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
  <aside class="session-drawer" :class="{ open }">
    <div class="drawer-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot red"></span>
        <span class="traffic-dot yellow"></span>
        <span class="traffic-dot green"></span>
      </div>
      <span class="window-filename">sessions --list</span>
      <button class="close-button" type="button" title="Close sessions" @click="emit('close')">
        <X :size="13" />
      </button>
    </div>

    <div class="drawer-toolbar">
      <button class="new-btn" type="button" @click="emit('create')">
        <Plus :size="12" />
        <span>New Session</span>
      </button>
    </div>

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

    <div v-if="sessionStore.sessions.length > 0" class="drawer-footer">
      <button class="clear-all-btn" type="button" @click="clearAllSessions">
        <Trash2 :size="12" />
        <span>Clear All Sessions</span>
      </button>
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

.drawer-toolbar,
.drawer-footer {
  padding: var(--space-8) var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.drawer-footer {
  border-top: 1px solid var(--color-border);
  border-bottom: 0;
}

.new-btn,
.clear-all-btn {
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

.session-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.session-item.active {
  background: var(--color-accent-muted);
  color: var(--color-accent);
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
</style>
