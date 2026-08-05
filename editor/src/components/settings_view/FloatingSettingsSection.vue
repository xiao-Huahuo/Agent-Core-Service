<!--
  悬浮窗设置区域组件。

  Usage:
    悬浮窗启用开关、三档置顶模式与手动唤起按钮。
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

    <div class="setting-row toggle-row">
      <label>启用悬浮窗</label>
      <input
        type="checkbox"
        :checked="settingsStore.floatingEnabled"
        @change="settingsStore.setFloatingEnabled(($event.target as HTMLInputElement).checked)"
      />
    </div>

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
      <label></label>
      <button
        class="add-btn"
        type="button"
        :disabled="!settingsStore.floatingEnabled"
        @click="handleOpenFloating"
      >
        打开悬浮窗
      </button>
    </div>

    <p class="setting-hint">悬浮窗可从托盘菜单唤起,也可固定在桌面其他窗口之上。</p>
  </div>
</template>
