<!--
  Agent session drawer.

  Usage:
  Slides out from the left side of the Agent panel and manages backend chat
  sessions for the current editor user_id.
-->
<script setup lang="ts">
import { PanelLeft, Plus, Trash2, X } from 'lucide-vue-next'
import logoSrc from '@/assets/images/无底图标.png'

import { useSessionStore } from '@/stores/session'
import type { SessionRecord } from '@/api/session'

const props = defineProps<{
  open: boolean
  userId: string
  mode?: 'panel' | 'page'
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
      <button class="brand-copy" type="button" @click="emit('create')">
        <img :src="logoSrc" class="brand-logo" alt="" />
        <strong>MetaWeave</strong>
      </button>
      <button class="close-button" type="button" title="收起侧边栏" @click="emit('close')">
        <PanelLeft :size="15" />
      </button>
    </div>

    <div class="drawer-toolbar">
      <div class="primary-actions">
        <button class="new-btn" type="button" @click="emit('create')">
          <span>新对话</span>
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
        <span class="session-name">{{ displayName(session) }}</span>
        <span class="session-time">{{ session.updated_at?.slice(0, 10) }}</span>
        <span class="delete-btn" title="删除会话" @click="deleteSession(session.session_id, $event)">
          <X :size="12" />
        </span>
      </button>
      <p v-if="!sessionStore.sessions.length" class="empty-hint">No sessions found</p>
    </div>

    <div class="drawer-footer">
      <button v-if="sessionStore.sessions.length > 0" class="clear-all-btn" type="button" @click="clearAllSessions">
        <Trash2 :size="12" />
        <span>清空全部</span>
      </button>
      <div class="user-strip">
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
  --drawer-page-hover: var(--color-primary-softer);
  --drawer-page-active: var(--color-primary-soft);
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
  border-radius: var(--radius-md);
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
  --drawer-page-hover: var(--color-primary-softer);
  --drawer-page-active: var(--color-primary-soft);
  top: 0;
  bottom: 0;
  left: 0;
  width: 280px;
  max-width: min(280px, 80vw);
  border: 0;
  border-radius: 0;
  background: var(--color-canvas-soft);
  box-shadow: none;
  backdrop-filter: none;
  transform: translateX(calc(-100% + 10px));
}

:root[data-theme="light"] .session-drawer.page-mode {
  --drawer-page-hover: var(--color-primary-softer);
  --drawer-page-active: var(--color-primary-soft);
}

.session-drawer.page-mode.open {
  transform: translateX(0);
}

.drawer-titlebar {
  grid-template-columns: minmax(0, 1fr) auto;
  display: grid;
  align-items: center;
  gap: var(--space-8);
  min-height: 58px;
  padding: 0 var(--space-20);
  border-bottom: 0;
  background: transparent;
}

.brand-copy {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  color: inherit;
  font: inherit;
  padding: 0;
}

.brand-logo {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.brand-copy strong {
  overflow: hidden;
  color: var(--color-text-primary);
  font-family: var(--font-ui);
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
  font-family: var(--font-ui);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-tertiary);
}

.close-button:hover {
  background: var(--drawer-page-hover);
  color: var(--color-text-primary);
}

.drawer-toolbar {
  padding: 0 0 var(--space-14);
  border-bottom: 0;
}

.drawer-footer {
  display: grid;
  gap: var(--space-10);
  padding: var(--space-12);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 0;
}

.new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 36px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 600;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  min-width: 36px;
  min-height: 36px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.clear-all-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  min-height: 34px;
  padding: var(--space-8) var(--space-12);
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.primary-actions {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin: 0 var(--space-20);
}

.new-btn:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
  box-shadow: 0 8px 22px rgba(66, 36, 235, 0.14);
  transform: translateY(-1px);
}

.clear-all-btn:hover {
  border-color: rgba(197, 101, 101, 0.4);
  background: rgba(197, 101, 101, 0.08);
  color: #c56565;
  box-shadow: 0 8px 22px rgba(197, 101, 101, 0.12);
  transform: translateY(-1px);
}

.new-btn:active,
.clear-all-btn:active {
  box-shadow: none;
  transform: translateY(0) scale(0.98);
}

.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-12) var(--space-12) var(--space-8);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  min-height: 30px;
  margin-bottom: var(--space-2);
  padding: 0 var(--space-12);
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: 12px;
  text-align: left;
}

.session-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.session-item.active {
  border-color: color-mix(in srgb, var(--color-primary) 24%, var(--color-border));
  background: var(--drawer-page-active);
  color: var(--color-primary);
}

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
  font-family: var(--font-ui);
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
  font-family: var(--font-ui);
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
