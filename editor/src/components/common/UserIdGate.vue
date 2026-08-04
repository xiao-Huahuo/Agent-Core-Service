<!--
  Editor user id gate.

  Usage:
  Blocks the editor routes until a local user_id is entered. The value is stored
  through the settings store and will later be replaced by backend user settings.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import { ensureSettingsProfile } from '@/api/settings'
import darkTitle from '@/assets/images/暗色标题.png'
import lightTitle from '@/assets/images/亮色标题.png'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'
import { useSettingsStore } from '@/stores/settings'

defineOptions({ name: 'UserIdGate' })

const settingsStore = useSettingsStore()
const draftUserId = ref('')
const errorMessage = ref('')
const loading = ref(false)
const isDark = computed(() => settingsStore.isDark)
const welcomeTitleSrc = computed(() => isDark.value ? darkTitle : lightTitle)
const logoSrc = computed(() => isDark.value ? darkLogo : lightLogo)

async function submitUserId() {
  const normalizedUserId = draftUserId.value.trim()
  if (!normalizedUserId) {
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const profile = await ensureSettingsProfile(normalizedUserId)
    settingsStore.applyBackendProfile(profile)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to initialize user profile'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="user-gate">
    <img :src="logoSrc" class="gate-cap-icon" alt="" />
    <img :src="welcomeTitleSrc" class="gate-logo" alt="MetaWeave" />
    <form class="gate-panel" @submit.prevent="submitUserId">
      <div class="gate-copy">
        <h2>选择本地身份</h2>
        <p>输入一个 user_id 后，元织会加载对应的知识库、外观、模型与 Agent 设置。</p>
      </div>
      <label for="editor-user-id">用户 ID</label>
      <div class="input-row">
        <input
          id="editor-user-id"
          v-model="draftUserId"
          autocomplete="username"
          autofocus
          placeholder="例如: 1"
          type="text"
        />
        <button type="submit" :disabled="!draftUserId.trim() || loading">
          {{ loading ? '正在进入' : '进入' }}
        </button>
      </div>
      <p v-if="errorMessage" class="gate-error">{{ errorMessage }}</p>
      <p v-else class="gate-hint">这是本机身份标识，不需要注册账号。</p>
    </form>
  </main>
</template>

<style scoped>
.user-gate {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-12);
  width: 100%;
  height: 100%;
  background: var(--color-canvas);
  -webkit-app-region: drag;
}

.gate-cap-icon {
  display: block;
  width: 96px;
  height: auto;
  object-fit: contain;
  margin-bottom: -8px;
  animation: gate-fade-in 1.2s ease-out forwards;
  -webkit-app-region: no-drag;
}

.gate-logo {
  display: block;
  width: 240px;
  height: auto;
  object-fit: contain;
  animation: gate-fade-in 1.2s ease-out forwards;
  -webkit-app-region: no-drag;
}

@keyframes gate-fade-in {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.gate-panel {
  display: grid;
  gap: var(--space-12);
  width: min(420px, calc(100vw - 32px));
  padding: var(--space-20);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  -webkit-app-region: no-drag;
}

.gate-copy {
  display: grid;
  gap: var(--space-6);
}

.gate-copy h2 {
  margin: 0;
  color: var(--color-text);
  font-size: calc(18px * var(--font-scale));
  font-weight: 700;
  line-height: 1.25;
}

.gate-copy p,
.gate-hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.6;
}

label {
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
}

.input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-8);
}

input {
  min-width: 0;
  height: 34px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-canvas-soft);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
}

input:focus {
  border-color: var(--color-primary);
}

button {
  height: 34px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: white;
  font-size: calc(13px * var(--font-scale));
}

button:disabled {
  cursor: default;
  opacity: 0.42;
}

.gate-error {
  margin: 0;
  color: var(--color-danger);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.5;
}

@media (max-width: 520px) {
  .gate-panel {
    padding: var(--space-16);
  }

  .input-row {
    grid-template-columns: 1fr;
  }
}
</style>
