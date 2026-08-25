<!--
  Shared Agent sidebar titlebar.

  Usage:
  AgentPanel and the floating Agent render this same control surface so session,
  environment, task, child-Agent, expansion, new-chat, and render-mode controls
  cannot drift between windows. Native floating-window controls use the slot.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'

const props = withDefaults(defineProps<{
  title: string
  chatMode: 'chat' | 'tool'
  environmentOpen?: boolean
  taskOpen?: boolean
  childOpen?: boolean
  showEnvironment?: boolean
  compact?: boolean
  /** Replace compact panel expansion with the session-history toggle. */
  historyToggle?: boolean
  /** Optional branded history-toggle icon supplied by the full Agent surface. */
  sessionIconSrc?: string
  draggable?: boolean
}>(), {
  environmentOpen: false,
  taskOpen: false,
  childOpen: false,
  showEnvironment: true,
  compact: false,
  historyToggle: false,
  sessionIconSrc: '',
  draggable: false,
})

defineEmits<{
  toggleSessions: []
  toggleEnvironment: []
  toggleTask: []
  toggleChild: []
  expand: []
  create: []
  toggleChatMode: []
}>()
</script>

<template>
  <header class="agent-panel-titlebar" :class="{ compact: props.compact, 'history-toggle': props.historyToggle, draggable: props.draggable }">
    <button class="titlebar-button session-button" type="button" title="会话" @click="$emit('toggleSessions')">
      <img v-if="props.sessionIconSrc" :src="props.sessionIconSrc" class="titlebar-history-logo" alt="" />
      <IcIcon v-else name="forum" :size="16" />
    </button>
    <button class="titlebar-button expand-button" type="button" title="展开 Agent 页面" @click="$emit('expand')">
      <IcIcon name="open-in-full" :size="16" />
    </button>
    <div class="titlebar-title"><strong>{{ props.title }}</strong></div>
    <div class="titlebar-actions">
      <button v-if="props.showEnvironment" class="titlebar-button secondary-action" type="button" title="环境与变更" :aria-pressed="props.environmentOpen" @click="$emit('toggleEnvironment')"><IcIcon name="dns" :size="16" /></button>
      <button class="titlebar-button secondary-action" type="button" title="任务列表" :aria-pressed="props.taskOpen" @click="$emit('toggleTask')"><IcIcon name="checklist" :size="16" /></button>
      <button class="titlebar-button secondary-action" type="button" title="子 Agent" :aria-pressed="props.childOpen" @click="$emit('toggleChild')"><IcIcon name="group" :size="16" /></button>
      <button class="new-session-button" type="button" title="新对话" @click="$emit('create')"><IcIcon name="add" :size="17" /><span>新对话</span></button>
      <button class="render-mode-button secondary-action" type="button" title="切换对话渲染模式" @click="$emit('toggleChatMode')"><IcIcon name="history" :size="15" /><span>{{ props.chatMode }}</span></button>
      <slot name="window-controls" />
    </div>
  </header>
</template>

<style scoped>
.agent-panel-titlebar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  min-height: 32px;
  padding: 0 var(--space-10);
  background: transparent;
}

.agent-panel-titlebar.draggable { -webkit-app-region: drag; }
.agent-panel-titlebar.draggable button { -webkit-app-region: no-drag; }
.titlebar-title { min-width: 0; }
.titlebar-title strong { display: block; overflow: hidden; color: var(--color-text-primary); font-size: calc(13px * var(--font-scale)); font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.titlebar-actions { display: flex; align-items: center; gap: var(--space-4); }
.titlebar-button,
.render-mode-button,
.new-session-button { display: inline-flex; align-items: center; justify-content: center; height: 26px; border: 0; font: inherit; cursor: pointer; }
.titlebar-button { width: 28px; border-radius: 999px; background: transparent; color: var(--color-text-tertiary); }
.titlebar-history-logo { display: block; width: 18px; height: 18px; object-fit: contain; }
.titlebar-button:hover,
.titlebar-button[aria-pressed="true"],
.render-mode-button:hover { background: var(--color-accent-muted); color: var(--color-text-primary); }
.render-mode-button { gap: var(--space-4); padding: 0 var(--space-8); border-radius: 999px; background: transparent; color: var(--color-text-tertiary); font-size: calc(10px * var(--font-scale)); }
.new-session-button { gap: var(--space-6); padding: 0 var(--space-10); border-radius: 999px; background: var(--color-primary); color: #fff; font-size: calc(13px * var(--font-scale)); }
.new-session-button:hover { background: var(--color-primary-hover, var(--color-primary)); }
.expand-button { display: none; }

.agent-panel-titlebar.compact .session-button,
.agent-panel-titlebar.compact .secondary-action { display: none; }
.agent-panel-titlebar.compact .expand-button { display: inline-flex; }
.agent-panel-titlebar.compact.history-toggle .session-button { display: inline-flex; }
.agent-panel-titlebar.compact.history-toggle .expand-button { display: none; }

@media (max-width: 480px) {
  .new-session-button span,
  .render-mode-button span { display: none; }
  .new-session-button { width: 28px; padding: 0; }
}
</style>
