<!--
  应用顶栏 — macOS 窗口标题栏。
  红绿灯 + 标签导航 + 绝对居中会话标题 + 主题切换。
-->

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import ThemeToggle from './ThemeToggle.vue'

const route = useRoute()
const sessionStore = useSessionStore()

const title = computed(() => {
  const name = sessionStore.currentSession?.session_name
  return name || 'agent-console ~/chat'
})

function isActive(path) {
  if (path === '/chat') return route.path === '/' || route.path.startsWith('/chat')
  return route.path.startsWith(path)
}
</script>

<template>
  <div class="macos-card-titlebar">
    <!-- 红绿灯 -->
    <div class="traffic-lights">
      <span class="traffic-dot red"></span>
      <span class="traffic-dot yellow"></span>
      <span class="traffic-dot green"></span>
    </div>

    <!-- 标签导航 -->
    <nav class="tabs">
      <RouterLink to="/chat" class="tab" :class="{ active: isActive('/chat') }">
        Chat
      </RouterLink>
      <RouterLink to="/dashboard" class="tab" :class="{ active: isActive('/dashboard') }">
        Obs
      </RouterLink>
    </nav>

    <!-- 绝对居中标题 -->
    <span class="window-title">{{ title }}</span>

    <div class="spacer"></div>

    <span class="window-status">ready</span>
    <ThemeToggle />
  </div>
</template>

<style scoped>
.macos-card-titlebar {
  position: relative;
}

.window-title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 40%;
  pointer-events: none;
}

.tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: var(--space-10);
  flex-shrink: 0;
}

.tab {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 3px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.tab:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.tab.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.35);
  background: var(--color-accent-muted);
}

.spacer {
  flex: 1;
}
</style>
