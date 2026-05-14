/*
 * 全局设置 Store。
 *
 * 功能说明:
 * 管理明暗主题切换与全局配色方案,状态持久化到 localStorage,
 * 通过设置 document.documentElement 的 data-theme 属性驱动 CSS 变量切换。
 * 所有主题相关逻辑必须经过本 Store,禁止在组件中自行操作 DOM 或 localStorage。
 *
 * 使用说明:
 * import { useSettingsStore } from '@/stores/settings'
 * const settings = useSettingsStore()
 * settings.toggleTheme()   // 切换明暗
 * settings.initTheme()     // 应用启动时调用一次,从 localStorage 恢复
 */

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

const THEME_KEY = 'agent_console_theme'

/**
 * 从 localStorage 读取持久化的主题设置。
 * 返回空字符串表示尚未设置,后续由 initTheme 根据系统偏好决定。
 */
function loadTheme() {
  return localStorage.getItem(THEME_KEY)
}

/**
 * 将主题写入 localStorage。
 */
function saveTheme(theme) {
  localStorage.setItem(THEME_KEY, theme)
}

export const useSettingsStore = defineStore('settings', () => {
  /* ================================================================
   * 状态
   * ================================================================ */

  /** @type {import('vue').Ref<'dark'|'light'>} */
  const themeMode = ref(loadTheme() || '')

  /** 全局配色方案,预留扩展 */
  const colorScheme = ref('default')

  /* ================================================================
   * 内部方法
   * ================================================================ */

  /**
   * 将当前主题应用到 DOM,设置 <html> 的 data-theme 属性。
   */
  function applyTheme() {
    document.documentElement.setAttribute('data-theme', themeMode.value)
  }

  /* ================================================================
   * 公开方法
   * ================================================================ */

  /**
   * 在应用挂载前调用,从 localStorage 恢复主题。
   * 若未设置则默认使用深色主题,避免页面闪烁。
   */
  function initTheme() {
    if (!themeMode.value) {
      themeMode.value = 'dark'
      saveTheme('dark')
    }
    applyTheme()
  }

  /**
   * 在明暗主题之间切换。
   */
  function toggleTheme() {
    themeMode.value = themeMode.value === 'dark' ? 'light' : 'dark'
    saveTheme(themeMode.value)
    applyTheme()
  }

  return {
    themeMode,
    colorScheme,
    initTheme,
    toggleTheme,
  }
})
