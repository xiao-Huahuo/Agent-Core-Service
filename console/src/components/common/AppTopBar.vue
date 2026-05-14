<!--
  应用顶栏 — macOS 窗口标题栏。
  红绿灯 + 文件名 + 侧边栏切换 + 标签导航 + 主题切换。
-->

<script setup>
import { useRoute } from 'vue-router'
import { Menu } from 'lucide-vue-next'
import ThemeToggle from './ThemeToggle.vue'

defineProps({
  showMenuBtn: { type: Boolean, default: false },
})

const emit = defineEmits(['toggleSidebar'])

const route = useRoute()

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

    <!-- 侧边栏切换 -->
    <button v-if="showMenuBtn" class="menu-btn" @click="$emit('toggleSidebar')">
      <Menu :size="13" />
    </button>

    <!-- 文件名 -->
    <span class="window-filename">agent-console ~/chat</span>

    <!-- 标签导航 -->
    <nav class="tabs">
      <RouterLink to="/chat" class="tab" :class="{ active: isActive('/chat') }">
        Chat
      </RouterLink>
      <RouterLink to="/dashboard" class="tab" :class="{ active: isActive('/dashboard') }">
        Obs
      </RouterLink>
    </nav>

    <!-- 填充 -->
    <div class="spacer"></div>

    <!-- 状态 + 主题 -->
    <span class="window-status">ready</span>
    <ThemeToggle />
  </div>
</template>

<style scoped>
.menu-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.menu-btn:hover {
  color: var(--color-text-primary);
  border-color: var(--color-border-strong);
  background: var(--color-bg-hover);
}

.tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: var(--space-12);
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
