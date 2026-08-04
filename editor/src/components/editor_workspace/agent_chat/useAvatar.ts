/*
 * Agent chat avatar helper.
 *
 * Usage:
 * Provides the same avatar assets as console chat while keeping the user's
 * random avatar stable during the current renderer session.
 */

import { computed, ref } from 'vue'

import agentAvatarLight from '@/assets/images/亮色无底图标.png'
import agentAvatarDark from '@/assets/images/暗色无底图标.png'
import avatar1 from '@/assets/images/avatar/乌萨奇.jpg'
import avatar2 from '@/assets/images/avatar/吉伊.jpg'
import avatar3 from '@/assets/images/avatar/小八.jpg'
import { useSettingsStore } from '@/stores/settings'

const userAvatarPool = [avatar1, avatar2, avatar3]
const userAvatar = ref('')

export function useAvatar() {
  if (!userAvatar.value) {
    userAvatar.value = userAvatarPool[Math.floor(Math.random() * userAvatarPool.length)] ?? avatar1
  }
  const settingsStore = useSettingsStore()
  const agentAvatar = computed(() => settingsStore.isDark ? agentAvatarDark : agentAvatarLight)
  return {
    userAvatar,
    agentAvatar,
  }
}
