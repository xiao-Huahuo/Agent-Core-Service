/*
 * Agent Console 应用入口。
 *
 * 功能说明:
 * 本文件初始化 Vue 应用、Pinia 状态管理与 Vue Router,挂载到 #app。
 * 在 mount 前引入全局样式并应用持久化的主题设置。
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useSettingsStore } from './stores/settings'

import '@/assets/main.css'
import '@/assets/hljs-theme.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

/* 在挂载前从 localStorage 恢复主题,避免页面闪烁 */
const settingsStore = useSettingsStore()
settingsStore.initTheme()

app.mount('#app')
