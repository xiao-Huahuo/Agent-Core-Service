<!--
  Favorite session list.

  Usage:
  Renders only backend-persisted favorite Agent sessions in the Favorites page.
  This component intentionally excludes drawer-only controls such as new chat,
  import, and clear-all actions.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import FavoriteButton from '@/components/common/FavoriteButton.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useSessionStore } from '@/stores/session'
import type { SessionRecord } from '@/api/session'
import { exportSession } from '@/utils/sessionExport'

defineOptions({ name: 'FavoriteSessionList' })

const props = defineProps<{
  userId: string
}>()

const emit = defineEmits<{
  select: [sessionId: string]
}>()

const sessionStore = useSessionStore()
const favoritesStore = useFavoritesStore()
const exportingId = ref<string | null>(null)

const favoriteSessions = computed(() => {
  const favoriteIds = favoritesStore.idsFor('session', '')
  return sessionStore.sessions.filter((session) => favoriteIds.has(session.session_id))
})

watch(
  () => props.userId,
  (userId) => {
    if (!userId) return
    void Promise.all([
      sessionStore.load(userId),
      favoritesStore.load(userId, 'session', ''),
    ])
  },
  { immediate: true },
)

function displayName(session: SessionRecord) {
  return session.session_name || session.session_id.slice(0, 8)
}

function displayDate(session: SessionRecord) {
  return session.updated_at?.slice(0, 10) || '-'
}

function selectSession(sessionId: string) {
  sessionStore.select(sessionId)
}

function openSession(sessionId: string) {
  sessionStore.select(sessionId)
  emit('select', sessionId)
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

async function deleteSession(sessionId: string, event: Event) {
  event.stopPropagation()
  await sessionStore.remove(sessionId)
}
</script>

<template>
  <section class="favorite-session-list" aria-label="收藏会话">
    <div class="session-list-header" aria-hidden="true">
      <span>会话名</span>
      <span>日期</span>
      <span>导出</span>
      <span>收藏</span>
      <span>删除</span>
    </div>
    <div
      v-for="(session, index) in favoriteSessions"
      :key="session.session_id"
      class="favorite-session-row"
      :class="{ active: session.session_id === sessionStore.currentSessionId }"
      :style="{ animationDelay: `${Math.min(index, 24) * 18}ms` }"
      role="button"
      tabindex="0"
      @click="selectSession(session.session_id)"
      @dblclick="openSession(session.session_id)"
      @keydown.enter.prevent="openSession(session.session_id)"
      @keydown.space.prevent="selectSession(session.session_id)"
    >
      <span class="session-name">{{ displayName(session) }}</span>
      <time class="session-date">{{ displayDate(session) }}</time>
      <span
        class="row-icon-btn"
        :class="{ loading: exportingId === session.session_id }"
        title="导出会话"
        @click="exportSessionHandler(session, $event)"
      >
        <IcIcon name="upload" :size="15" />
      </span>
      <span class="row-icon-btn">
        <FavoriteButton target-type="session" :target-id="session.session_id" />
      </span>
      <span class="row-icon-btn danger" title="删除会话" @click="deleteSession(session.session_id, $event)">
        <IcIcon name="close" :size="15" />
      </span>
    </div>
    <p v-if="!favoriteSessions.length" class="empty-hint">没有收藏的会话</p>
  </section>
</template>

<style scoped>
.favorite-session-list {
  display: block;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  padding: 0;
  overflow: auto;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
}

.session-list-header,
.favorite-session-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 132px 72px 72px 72px;
  align-items: center;
  column-gap: var(--space-12);
  min-height: 34px;
  padding: 0 var(--space-12);
  font-family: var(--font-ui);
  line-height: 1;
}

.session-list-header {
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 0;
  background: var(--color-canvas);
  color: var(--color-text-tertiary);
  font-size: calc(12px * var(--font-scale));
  font-weight: 500;
}

.favorite-session-row {
  width: 100%;
  height: 34px;
  border: 0;
  border-bottom: 1px solid rgba(127, 127, 127, 0.12);
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  text-align: left;
  cursor: pointer;
  opacity: 0;
  transform-origin: top;
  animation: session-row-drop 170ms ease-out both;
}

.session-list-header > span,
.favorite-session-row > span,
.favorite-session-row > time {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.favorite-session-row:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.favorite-session-row.active {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.session-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-date {
  color: var(--color-text-tertiary);
}

.row-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  border-radius: 50%;
  color: var(--color-text-tertiary);
  justify-self: start;
  transition:
    background 160ms ease,
    color 160ms ease;
}

.row-icon-btn:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.row-icon-btn.danger:hover {
  background: rgba(197, 101, 101, 0.08);
  color: #c56565;
}

.row-icon-btn.loading {
  animation: export-pulse 0.8s ease-in-out infinite;
}

.empty-hint {
  padding: var(--space-24);
  color: var(--color-text-tertiary);
  font-size: calc(13px * var(--font-scale));
  text-align: center;
}

@keyframes export-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

@keyframes session-row-drop {
  from {
    opacity: 0;
    transform: scaleY(0.94) translateY(-3px);
  }

  to {
    opacity: 1;
    transform: scaleY(1) translateY(0);
  }
}
</style>
