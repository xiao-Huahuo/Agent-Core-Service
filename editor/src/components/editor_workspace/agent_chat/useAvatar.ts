/*
 * Agent chat avatar helper.
 *
 * Usage:
 * Provides the same avatar assets as console chat while keeping the user's
 * random avatar stable during the current renderer session.
 */

import { ref } from 'vue'

import agentAvatar from '@/assets/images/无底图标.png'
import avatar1 from '@/assets/images/avatar/乌萨奇.jpg'
import avatar2 from '@/assets/images/avatar/吉伊.jpg'
import avatar3 from '@/assets/images/avatar/小八.jpg'

const userAvatarPool = [avatar1, avatar2, avatar3]
const userAvatar = ref('')

export function useAvatar() {
  if (!userAvatar.value) {
    userAvatar.value = userAvatarPool[Math.floor(Math.random() * userAvatarPool.length)] ?? avatar1
  }
  return {
    userAvatar,
    agentAvatar,
  }
}
