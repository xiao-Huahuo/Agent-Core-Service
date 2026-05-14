<!--
  会话行 — 终端风格。
-->

<script setup>
defineProps({
  session: { type: Object, required: true },
  isActive: { type: Boolean, default: false },
})

defineEmits(['select'])

function displayName(session) {
  return session.session_name || session.session_id.slice(0, 8)
}
</script>

<template>
  <button
    class="session-item"
    :class="{ active: isActive }"
    @click="$emit('select', session.session_id)"
  >
    <span class="session-icon">$</span>
    <span class="session-name">{{ displayName(session) }}</span>
    <span class="session-time">{{ session.updated_at?.slice(0, 10) }}</span>
  </button>
</template>

<style scoped>
.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-8) var(--space-12);
  border: none;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-fast);
}

.session-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.session-item.active {
  background: var(--color-accent-muted);
  border-left-color: var(--color-accent);
  color: var(--color-accent);
}

.session-icon {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

.session-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.session-time {
  font-size: 9px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
</style>
