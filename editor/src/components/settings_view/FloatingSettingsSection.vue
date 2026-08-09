<!--
  悬浮窗设置区域组件。

  Usage:
    三档置顶模式与启动悬浮窗开关。启动开关保存到用户设置,并同步桌面悬浮窗显隐。
    <FloatingSettingsSection />
-->
<script setup lang="ts">
import { ref } from 'vue'

import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const saving = ref(false)

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
</script>

<template>
  <div class="setting-section">
    <h3>悬浮窗设置</h3>

    <div class="setting-row">
      <label>置顶模式</label>
      <div class="theme-row">
        <button
          v-for="opt in PIN_MODE_OPTIONS"
          :key="opt.value"
          type="button"
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
      <span class="toggle-hint">{{ settingsStore.profile.floatingLaunchEnabled ? '已开启' : '已关闭' }}</span>
    </div>

    <p class="setting-hint">开启后立即显示悬浮窗,并在桌面端下次启动主窗口时自动显示;关闭后立即隐藏悬浮窗。</p>
  </div>
</template>
