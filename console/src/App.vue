<!--
  Agent Console 根组件 — 双 macOS 窗口卡片并列布局。
  左侧: 会话列表面板 (独立 macOS 卡片)
  右侧: 主聊天窗口 (独立 macOS 卡片, 填满剩余空间)
-->

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Trash2, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import { useUserId } from '@/composable/useUserId'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import AppTopBar from '@/components/common/AppTopBar.vue'
import SessionItem from '@/components/session/SessionItem.vue'

const route = useRoute()
const { userId, hasUserId } = useUserId()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const sidebarOpen = ref(true)
const isMobile = ref(window.innerWidth < 768)

function onResize() { isMobile.value = window.innerWidth < 768 }
if (typeof window !== 'undefined') {
  window.addEventListener('resize', onResize)
}

/** 是否显示侧边栏 (仅 /chat 路由 + 已登录) */
function showSidebar() {
  return hasUserId.value && (route.path === '/' || route.path.startsWith('/chat'))
}

function selectSession(sessionId) {
  sessionStore.select(sessionId)
  chatStore.clear()
  chatStore.loadHistory(sessionId, userId.value)
  if (isMobile.value) sidebarOpen.value = false
}

async function handleCreate() {
  if (!userId.value) return
  const sessionId = await sessionStore.create(userId.value)
  selectSession(sessionId)
}

async function handleDelete(sessionId) {
  await sessionStore.remove(sessionId)
}

async function handleClearAll() {
  if (!userId.value || sessionStore.sessions.length === 0) return
  if (!window.confirm('确认清空全部会话？此操作不可撤销。')) return
  await sessionStore.clearAll(userId.value)
}

onMounted(async () => {
  if (hasUserId.value) {
    await sessionStore.load(userId.value)
  }
})
</script>

<template>
  <div class="app-shell">
    <!-- ============================================================
         左侧: 会话列表面板 (独立 macOS 卡片)
         ============================================================ -->
    <Transition name="sidebar-slide">
      <aside v-if="showSidebar() && sidebarOpen && !isMobile" class="sidebar-card macos-card">
        <!-- 切换按钮,溢出在侧边栏右侧 -->
        <button
          v-if="showSidebar()"
          class="sidebar-toggle-outside"
          @click="sidebarOpen = false"
        >
          <PanelLeftClose :size="13" />
        </button>
        <div class="macos-card-titlebar">
          <div class="traffic-lights">
            <span class="traffic-dot sm red"></span>
            <span class="traffic-dot sm yellow"></span>
            <span class="traffic-dot sm green"></span>
          </div>
          <span class="window-filename">会话记录</span>
          <span class="window-status">{{ sessionStore.sessions.length }} total</span>
        </div>

        <div class="sidebar-toolbar">
          <button class="new-btn" @click="handleCreate">
            <Plus :size="13" />
            <span>New Session</span>
          </button>
        </div>

        <div class="session-list">
          <SessionItem
            v-for="s in sessionStore.sessions"
            :key="s.session_id"
            :session="s"
            :is-active="s.session_id === sessionStore.currentSessionId"
            @select="selectSession"
            @delete="handleDelete"
          />
          <p v-if="!sessionStore.sessions.length" class="empty-hint">
            $ no sessions found
          </p>
        </div>

        <div v-if="sessionStore.sessions.length > 0" class="sidebar-footer">
          <button class="clear-all-btn" @click="handleClearAll">
            <Trash2 :size="12" />
            <span>清空全部会话</span>
          </button>
        </div>
      </aside>
    </Transition>

    <!-- 移动端抽屉 -->
    <Transition name="fade">
      <div v-if="showSidebar() && isMobile && sidebarOpen" class="drawer-overlay" @click="sidebarOpen = false"></div>
    </Transition>
    <Transition name="slide">
      <aside v-if="showSidebar() && isMobile && sidebarOpen" class="sidebar-card macos-card drawer-mobile">
        <button
          v-if="showSidebar()"
          class="sidebar-toggle-outside mobile-toggle"
          @click="sidebarOpen = false"
        >
          <PanelLeftClose :size="13" />
        </button>
        <div class="macos-card-titlebar">
          <div class="traffic-lights">
            <span class="traffic-dot sm red"></span>
            <span class="traffic-dot sm yellow"></span>
            <span class="traffic-dot sm green"></span>
          </div>
          <span class="window-filename">会话记录</span>
          <button class="drawer-close" @click="sidebarOpen = false">&times;</button>
        </div>
        <div class="sidebar-toolbar">
          <button class="new-btn" @click="handleCreate">
            <Plus :size="13" />
            <span>New Session</span>
          </button>
        </div>
        <div class="session-list">
          <SessionItem
            v-for="s in sessionStore.sessions"
            :key="s.session_id"
            :session="s"
            :is-active="s.session_id === sessionStore.currentSessionId"
            @select="selectSession"
            @delete="handleDelete"
          />
          <p v-if="!sessionStore.sessions.length" class="empty-hint">
            $ no sessions found
          </p>
        </div>

        <div v-if="sessionStore.sessions.length > 0" class="sidebar-footer">
          <button class="clear-all-btn" @click="handleClearAll">
            <Trash2 :size="12" />
            <span>清空全部会话</span>
          </button>
        </div>
      </aside>
    </Transition>

    <!-- ============================================================
         右侧: 主聊天窗口
         ============================================================ -->
    <div class="main-window macos-card">
      <AppTopBar />
      <div class="window-body">
        <router-view />
      </div>
    </div>

    <!-- 侧边栏关闭时的重开按钮 -->
    <button
      v-if="showSidebar() && !sidebarOpen"
      class="sidebar-reopen-btn"
      @click="sidebarOpen = true"
    >
      <PanelLeftOpen :size="14" />
    </button>
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  z-index: 1;
  height: 100vh;
  display: flex;
  padding: 2rem;
  gap: 1rem;
  overflow: hidden;
}

/* ================================================================
   侧边栏卡片 (独立 macOS 窗口)
   ================================================================ */

.sidebar-card {
  width: 260px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  box-shadow: var(--shadow-window);
  position: relative;
}

.sidebar-toolbar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.new-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-10);
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
  padding: var(--space-24);
  text-align: center;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.sidebar-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--color-border);
}

.clear-all-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.clear-all-btn:hover {
  color: #c56565;
  border-color: rgba(197, 101, 101, 0.4);
  background: rgba(197, 101, 101, 0.08);
}

/* ================================================================
   移动端抽屉
   ================================================================ */

.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0.5);
}

.drawer-mobile {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 310;
  width: 280px;
  overflow: hidden;
  border-radius: 0;
  border-top: none;
  border-bottom: none;
}

.mobile-toggle {
  right: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.drawer-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}

.drawer-close:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

/* 侧边栏内侧关闭按钮 (溢出右侧) */

.sidebar-toggle-outside {
  position: absolute;
  right: -22px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 52px;
  border: 1px solid var(--color-border);
  border-left: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--color-bg-card);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.sidebar-toggle-outside:hover {
  color: var(--color-text-primary);
  border-color: var(--color-accent);
  background: var(--color-bg-muted);
}

/* 侧边栏关闭时的浮动重开按钮 */
.sidebar-reopen-btn {
  position: absolute;
  top: 50%;
  left: 1.5rem;
  transform: translateY(-50%);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 52px;
  border: 1px solid var(--color-border);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--color-bg-card);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.sidebar-reopen-btn:hover {
  color: var(--color-text-primary);
  border-color: var(--color-accent);
  background: var(--color-bg-muted);
}

/* ================================================================
   主聊天窗口
   ================================================================ */

.main-window {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  box-shadow: var(--shadow-window);
}

.window-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ================================================================
   过渡动画
   ================================================================ */

.sidebar-slide-enter-active,
.sidebar-slide-leave-active {
  transition: width 200ms ease-out, min-width 200ms ease-out, opacity 150ms ease-out;
}
.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  width: 0 !important;
  min-width: 0 !important;
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 180ms ease-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 200ms ease-out;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}

@media (max-width: 768px) {
  .app-shell {
    height: 100vh;
    height: 100dvh;
    padding: 0;
    gap: 0;
  }
  .main-window {
    border-radius: 0;
    border: none;
  }
  .sidebar-reopen-btn {
    left: 4px;
  }
}
</style>
