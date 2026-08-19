<!--
  悬浮窗设置区域组件。

  Usage:
    三档置顶模式与启动悬浮窗开关。启动开关保存到用户设置,并同步桌面悬浮窗显隐。
    <FloatingSettingsSection />
-->
<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const saving = ref(false)
const pinSwitchRef = ref<HTMLElement | null>(null)
const pinSliderStyle = ref({ width: '0px', left: '0px' })

const PIN_MODE_OPTIONS: Array<{ value: 'off' | 'normal' | 'global'; label: string }> = [
  { value: 'off', label: '不置顶' },
  { value: 'normal', label: '普通置顶' },
  { value: 'global', label: '全局置顶' },
]

async function handleFloatingLaunchToggle(event: Event) {
  const enabled = (event.target as HTMLInputElement).checked
  saving.value = true
  try {
    await settingsStore.saveFloatingSettings({ floatingLaunchEnabled: enabled })
    await window.agentEditorDesktop?.floatingSetVisible?.(enabled)
    workspaceStore.showToast('悬浮窗设置已保存')
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '保存悬浮窗设置失败')
  } finally {
    saving.value = false
  }
}

function updatePinSlider() {
  void nextTick(() => {
    const container = pinSwitchRef.value
    const active = container?.querySelector<HTMLElement>('.settings-resource-page-button.active')
    if (!active) return
    pinSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

onMounted(updatePinSlider)
watch(() => settingsStore.floatingPinMode, updatePinSlider)
</script>

<template>
  <div class="setting-section">
    <h3>悬浮窗设置</h3>

    <div class="setting-row">
      <label>置顶模式</label>
      <div ref="pinSwitchRef" class="settings-resource-page-switch" role="radiogroup" aria-label="置顶模式">
        <span class="settings-resource-page-slider" :style="pinSliderStyle" aria-hidden="true"></span>
        <button
          v-for="opt in PIN_MODE_OPTIONS"
          :key="opt.value"
          class="settings-resource-page-button"
          type="button"
          role="radio"
          :aria-checked="settingsStore.floatingPinMode === opt.value"
          :class="{ active: settingsStore.floatingPinMode === opt.value }"
          @click="settingsStore.setFloatingPinMode(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <div class="setting-row toggle-row">
      <label>启动小窗</label>
      <input
        type="checkbox"
        :checked="Boolean(settingsStore.profile.floatingLaunchEnabled)"
        :disabled="saving"
        aria-label="启动时显示悬浮窗"
        @change="handleFloatingLaunchToggle"
      />
    </div>

    <p class="setting-hint">开启后立即显示悬浮窗,并在桌面端下次启动主窗口时自动显示;关闭后立即隐藏悬浮窗。</p>
  </div>
</template>

<style scoped>
.toggle-hint,
.setting-hint {
  display: none;
}

.settings-resource-page-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.settings-resource-page-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-softer);
  pointer-events: none;
  transition: left 250ms ease, width 250ms ease;
}

.settings-resource-page-button {
  position: relative;
  z-index: 1;
  height: 28px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
}

.settings-resource-page-button.active,
.settings-resource-page-button:hover {
  color: var(--color-primary);
}
</style>
