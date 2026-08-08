<!--
  悬浮窗设置区域组件。

  Usage:
    三档置顶模式与"启动小窗"按钮。悬浮窗随主窗口启动,开合按钮在顶栏。
    <FloatingSettingsSection />
-->
<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const PIN_MODE_OPTIONS: Array<{ value: 'off' | 'normal' | 'global'; label: string }> = [
  { value: 'off', label: '不置顶' },
  { value: 'normal', label: '普通置顶' },
  { value: 'global', label: '全局置顶' },
]

function handleOpenFloating() {
  window.agentEditorDesktop?.floatingToggle()
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

    <div class="setting-row">
      <label>启动小窗</label>
      <button class="add-btn" type="button" @click="handleOpenFloating">
        打开悬浮窗
      </button>
    </div>

    <p class="setting-hint">悬浮窗随主窗口一同启动,可从顶栏按钮唤起,也可固定在桌面其他窗口之上。</p>
  </div>
</template>
