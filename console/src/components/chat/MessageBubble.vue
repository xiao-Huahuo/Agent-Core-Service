<!--
  MessageBubble —— 消息气泡路由组件。
  根据 settings.chatMode 在对话模式 / 工具模式之间切换。
-->

<script setup>
import { useSettingsStore } from '@/stores/settings'
import ChatBubble from './ChatBubble.vue'
import ToolBubble from './ToolBubble.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false },
  userAvatar: { type: String, default: '' },
  agentAvatar: { type: String, default: '' },
  showAvatar: { type: Boolean, default: true },
})

const settings = useSettingsStore()
</script>

<template>
  <ChatBubble
    v-if="settings.chatMode === 'chat'"
    v-bind="props"
  />
  <ToolBubble
    v-else
    v-bind="props"
  />
</template>
