/*
 * 头像管理。
 *
 * Agent 始终使用 "兵王.jpg",
 * 用户随机从其余三个角色中选一个, 会话期间保持不变。
 */

import { ref } from 'vue'

/* 静态导入 avatar 图片 */
import agentAvatar from '@/assets/images/avatar/兵王.jpg'
import avatar1 from '@/assets/images/avatar/乌萨奇.jpg'
import avatar2 from '@/assets/images/avatar/吉伊.jpg'
import avatar3 from '@/assets/images/avatar/小八.jpg'

const userAvatarPool = [avatar1, avatar2, avatar3]

/** 选中的用户头像 (懒随机) */
const _userAvatar = ref('')

export function useAvatar() {
  if (!_userAvatar.value) {
    const idx = Math.floor(Math.random() * userAvatarPool.length)
    _userAvatar.value = userAvatarPool[idx]
  }
  return {
    userAvatar: _userAvatar,
    agentAvatar: agentAvatar,
  }
}
