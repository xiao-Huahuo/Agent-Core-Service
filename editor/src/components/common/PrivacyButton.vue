<!--
  Privacy toggle button.

  Usage:
  Render before a favorite button for knowledge files or library items. It
  persists through PrivacyStore and stops parent row/card interactions.
-->
<script setup lang="ts">
import { computed } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import type { PrivacyTargetType } from '@/api/privacy'
import { usePrivacyStore } from '@/stores/privacy'

defineOptions({ name: 'PrivacyButton' })

const props = withDefaults(defineProps<{
  targetType: PrivacyTargetType
  targetId: string
  libraryId?: string
  size?: number
  disabled?: boolean
}>(), { libraryId: undefined, size: 15, disabled: false })

const privacyStore = usePrivacyStore()
const active = computed(() => privacyStore.isPrivate(props.targetType, props.targetId, props.libraryId))
const pending = computed(() => privacyStore.isPending(props.targetType, props.targetId, props.libraryId))
const buttonStyle = computed(() => ({
  '--privacy-button-size': `${Math.max(props.size + 9, 22)}px`,
}))

function togglePrivacy() {
  if (props.disabled || pending.value) return
  void privacyStore.toggle(props.targetType, props.targetId, props.libraryId)
}
</script>

<template>
  <button
    class="privacy-button"
    :class="{ active, pending }"
    type="button"
    :disabled="disabled || pending"
    :title="active ? '取消隐私化' : '隐私化'"
    :aria-label="active ? '取消隐私化' : '隐私化'"
    :aria-pressed="active"
    :style="buttonStyle"
    @click.stop.prevent="togglePrivacy"
    @dblclick.stop.prevent
    @mousedown.stop
  >
    <IcIcon :name="active ? 'visibility-off' : 'visibility'" :size="size" morph />
  </button>
</template>

<style scoped>
.privacy-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: var(--privacy-button-size);
  height: var(--privacy-button-size);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color var(--transition-fast), opacity var(--transition-fast), transform 100ms ease;
}

.privacy-button:hover:not(:disabled),
.privacy-button.active {
  color: var(--color-primary);
}

.privacy-button:hover:not(:disabled) {
  transform: scale(1.1);
}

.privacy-button:disabled {
  cursor: default;
  opacity: 0.55;
}

@media (prefers-reduced-motion: reduce) {
  .privacy-button { transition: color var(--transition-fast), opacity var(--transition-fast); }
}
</style>
