<!--
  Agent session drawer.

  Usage:
  Slides out from the left side of the Agent panel and manages backend chat
  sessions for the current editor user_id.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useFavoritesStore } from '@/stores/favorites'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import type { SessionRecord } from '@/api/session'
import { exportSession } from '@/utils/sessionExport'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'
import lightTitle from '@/assets/images/亮色标题.png'
import darkTitle from '@/assets/images/暗色标题.png'

const props = defineProps<{
  open: boolean
  userId: string
  mode?: 'panel' | 'page'
  /** The panel-local session highlighted by this drawer. */
  selectedSessionId?: string
  /** Sessions with an active Agent stream, rendered with a compact spinner. */
  streamingSessionIds?: string[]
}>()

const emit = defineEmits<{
  close: []
  create: []
  select: [sessionId: string]
}>()

const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const favoritesStore = useFavoritesStore()
const titleSrc = computed(() => settingsStore.isDark ? darkTitle : lightTitle)
const logoSrc = computed(() => settingsStore.isDark ? darkLogo : lightLogo)
const exportingId = ref<string | null>(null)
const streamingSessionIdSet = computed(() => new Set([
  ...(props.streamingSessionIds ?? []),
  ...sessionStore.streamingSessionIds,
]))
const renderedSessions = computed(() => {
  return sessionStore.sessions
})

watch(
  () => props.userId,
  (userId) => {
    if (userId) void favoritesStore.load(userId, 'session', '')
  },
  { immediate: true },
)

onMounted(() => {
  if (props.userId) {
    void favoritesStore.load(props.userId, 'session', '')
  }
})

function displayName(session: SessionRecord) {
  return session.session_name || session.session_id.slice(0, 8)
}

function selectSession(sessionId: string) {
  emit('select', sessionId)
}

function toggleSessionFavorite(sessionId: string, event: Event) {
  event.stopPropagation()
  void favoritesStore.toggle('session', sessionId, '')
}

async function deleteSession(sessionId: string, event: Event) {
  event.stopPropagation()
  await sessionStore.remove(sessionId)
}

async function exportSessionHandler(session: SessionRecord, event: Event) {
  event.stopPropagation()
  if (exportingId.value) return
  exportingId.value = session.session_id
  try {
    await exportSession(session, props.userId)
  } catch (error) {
    console.error('导出会话失败:', error)
  } finally {
    exportingId.value = null
  }
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
        <img :src="titleSrc" class="brand-title" alt="MetaWeave" />
      </button>
      <button class="drawer-collapse-btn" type="button" title="收起侧边栏" @click="emit('close')">
        <IcIcon name="arrow-left" :size="18" />
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
      <div
        v-for="session in renderedSessions"
        :key="session.session_id"
        class="session-item"
        :class="{ active: session.session_id === (selectedSessionId || sessionStore.currentSessionId) }"
        role="button"
        tabindex="0"
        @click="selectSession(session.session_id)"
        @keydown.enter.prevent="selectSession(session.session_id)"
        @keydown.space.prevent="selectSession(session.session_id)"
      >
        <span class="session-name">{{ displayName(session) }}</span>
        <span v-if="streamingSessionIdSet.has(session.session_id)" class="session-streaming" aria-label="Agent 正在输出"></span>
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <button class="session-menu-btn" type="button" title="更多" aria-label="更多" @click.stop>
              <IcIcon name="more-horiz" :size="15" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuPortal>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                :class="{ favorited: favoritesStore.isFavorite('session', session.session_id, '') }"
                @select="toggleSessionFavorite(session.session_id, $event)"
              >
                <IcIcon name="star" :size="14" />
                <span>收藏</span>
              </DropdownMenuItem>
              <DropdownMenuLabel class="session-menu-date">
                <IcIcon name="calendar" :size="14" />
                <span>日期</span>
                <time>{{ session.updated_at?.slice(0, 10) }}</time>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem :disabled="Boolean(exportingId)" @select="exportSessionHandler(session, $event)">
                <IcIcon name="upload" :size="14" />
                <span>{{ exportingId === session.session_id ? '导出中' : '导出会话' }}</span>
              </DropdownMenuItem>
              <DropdownMenuItem variant="destructive" @select="deleteSession(session.session_id, $event)">
                <IcIcon name="close" :size="14" />
                <span>删除</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenu>
      </div>
      <p v-if="!renderedSessions.length" class="empty-hint">No sessions found</p>
    </div>

    <div class="drawer-footer">
      <button v-if="sessionStore.sessions.length > 0" class="clear-all-btn" type="button" @click="clearAllSessions">
        <IcIcon name="trash" :size="12" />
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
  border: 0;
  outline: none;
  border-radius: var(--radius-md);
  background: var(--color-chrome-rail-bg);
  transform: translateX(calc(-100% - 16px));
  transition:
    transform 200ms ease,
    opacity 160ms ease;
  opacity: 0;
  pointer-events: none;
}

.session-drawer.open {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
}

/* Mobile Agent main view mirrors the file tree's left-anchored floating panel. */
.session-drawer.mobile-floating {
  border: 1px solid var(--workspace-panel-border);
  border-radius: 18px;
  background: var(--color-bg-app);
  box-shadow: 12px 0 32px rgba(12, 18, 38, 0.22);
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
  outline: none;
  border-radius: var(--workspace-card-radius);
  background: var(--color-chrome-rail-bg);
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
  gap: var(--space-4);
  min-height: 58px;
  padding: 0 var(--space-20);
  border-bottom: 0;
  background: transparent;
}

.drawer-collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.drawer-collapse-btn:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-selection-blue);
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
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.brand-title {
  display: block;
  height: 22px;
  width: auto;
  object-fit: contain;
}

.session-streaming {
  width: 12px;
  height: 12px;
  margin-left: auto;
  flex: 0 0 auto;
  border: 1.5px solid var(--color-primary-soft);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: session-streaming-spin .7s linear infinite;
}

@keyframes session-streaming-spin { to { transform: rotate(360deg); } }


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
  font-size: calc(10px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
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
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  font-weight: 600;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease;
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
  font-size: calc(var(--font-size-xs) * var(--font-scale));
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
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  min-height: 30px;
  margin-bottom: var(--space-2);
  padding: 0 var(--space-12);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  text-align: left;
  cursor: pointer;
}

.session-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.session-item.active {
  background: var(--drawer-page-active);
  color: var(--color-primary);
}

.session-time {
  flex-shrink: 0;
  color: var(--color-text-tertiary);
}

.session-time {
  font-size: calc(9px * var(--font-scale));
}

.session-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-menu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  flex-shrink: 0;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition:
    background 160ms ease,
    color 160ms ease,
    opacity 160ms ease;
}

.session-menu-btn:hover,
.session-menu-btn[data-state='open'] {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.session-menu-date {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 30px;
  padding: 0 var(--space-8);
  font-size: calc(12px * var(--font-scale));
}

.ui-dropdown-item.favorited {
  color: #f2b705;
}

.session-menu-date {
  color: var(--color-text-tertiary);
}

.session-menu-date time {
  font-size: calc(10px * var(--font-scale));
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
  font-size: calc(9px * var(--font-scale));
}

.user-strip strong {
  display: block;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
