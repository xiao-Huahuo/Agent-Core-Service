<!--
  会话抽屉 — macOS 窗口卡片风格。
  从左侧滑入的独立 macOS 窗口。
-->

<script setup>
import { Plus } from 'lucide-vue-next'
import { useSessionStore } from '@/stores/session'
import { useUserId } from '@/composable/useUserId'
import SessionItem from './SessionItem.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const sessionStore = useSessionStore()
const { userId } = useUserId()

function close() { emit('update:modelValue', false) }

function selectSession(sessionId) {
  sessionStore.select(sessionId)
  emit('update:modelValue', false)
}

async function handleCreate() {
  if (!userId.value) return
  await sessionStore.create(userId.value)
}
</script>

<template>
  <Transition name="fade">
    <div v-if="modelValue" class="overlay" @click="close"></div>
  </Transition>

  <Transition name="slide">
    <aside v-if="modelValue" class="drawer macos-card">
      <!-- 标题栏 -->
      <div class="macos-card-titlebar">
        <div class="traffic-lights">
          <span class="traffic-dot sm red"></span>
          <span class="traffic-dot sm yellow"></span>
          <span class="traffic-dot sm green"></span>
        </div>
        <span class="window-filename">sessions --list</span>
        <span class="window-status">{{ sessionStore.sessions.length }} total</span>
      </div>

      <!-- 新建按钮 -->
      <div class="drawer-toolbar">
        <button class="new-btn" @click="handleCreate">
          <Plus :size="12" />
          <span>New Session</span>
        </button>
      </div>

      <!-- 会话列表 -->
      <div class="session-list">
        <SessionItem
          v-for="s in sessionStore.sessions"
          :key="s.session_id"
          :session="s"
          :is-active="s.session_id === sessionStore.currentSessionId"
          @select="selectSession"
        />
        <p v-if="!sessionStore.sessions.length" class="empty-hint">
          $ no sessions found
        </p>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.4);
}

.drawer {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 210;
  width: 300px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.05), 0 16px 48px rgba(0,0,0,0.5);
}

.drawer-toolbar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.new-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-btn:hover {
  color: var(--color-text-primary);
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.empty-hint {
  padding: var(--space-20);
  text-align: center;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

/* ---- 过渡动画 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 150ms ease-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 200ms ease-out;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.95);
}
</style>
