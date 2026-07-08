/*
 * Vue Router 路由配置。
 *
 * 功能说明:
 * 定义应用的路由表,包括聊天页面和观测面板页面。
 * 根路径 `/` 自动重定向到 `/chat`。
 *
 * 使用说明:
 * 由 main.js 导入并注册到 Vue 应用。
 */

import { createRouter, createWebHistory } from 'vue-router'

/** @type {import('vue-router').RouteRecordRaw[]} */
const routes = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
