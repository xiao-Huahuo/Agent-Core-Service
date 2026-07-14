/*
 * user_id 管理 composable。
 *
 * 功能说明:
 * 提供 user_id 的读写与响应式绑定。首次使用时从 localStorage 恢复,
 * 修改时同步写入 localStorage。不涉及任何认证逻辑。
 *
 * 使用说明:
 * const { userId, setUserId, hasUserId } = useUserId()
 * if (!hasUserId.value) { /* 显示输入框 * / }
 */

import { ref, computed } from 'vue'
import { getUserId as loadUserId, setUserId as saveUserId } from '@/api/client'
import { ensureUserProfile } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

/** @type {import('vue').Ref<string>} */
const userId = ref(loadUserId())

/**
 * user_id 管理 composable。
 */
export function useUserId() {
  /**
   * 是否已设置 user_id。
   */
  const hasUserId = computed(() => userId.value.length > 0)

  /**
   * 更新 user_id 并持久化到 localStorage。
   *
   * @param {string} id 新的 user_id
   */
  async function updateUserId(id) {
    const normalizedId = id.trim()
    const profile = await ensureUserProfile(normalizedId)
    const settingsStore = useSettingsStore()
    settingsStore.setUserProfile(profile)
    userId.value = profile.user_id
    saveUserId(profile.user_id)
    return profile
  }

  /**
   * 使用本地缓存的 user_id 从后端刷新用户设置档案。
   */
  async function refreshUserProfile() {
    if (!userId.value) {
      return null
    }
    return updateUserId(userId.value)
  }

  function clearUserId() {
    const settingsStore = useSettingsStore()
    settingsStore.setUserProfile(null)
    userId.value = ''
    saveUserId('')
  }

  return {
    userId,
    hasUserId,
    setUserId: updateUserId,
    refreshUserProfile,
    clearUserId,
  }
}
