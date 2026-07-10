/*
 * Page router for the editor front-end.
 *
 * Usage:
 * Register page-level routes only in this file. Components should navigate by
 * route name or path and must not create ad-hoc route tables elsewhere.
 */
import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'

const createHistory = window.agentEditorDesktop?.isDesktop ? createWebHashHistory : createWebHistory

const router = createRouter({
  history: createHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'workspace',
      component: () => import('@/views/EditorWorkspace.vue'),
    },
  ],
})

export default router
