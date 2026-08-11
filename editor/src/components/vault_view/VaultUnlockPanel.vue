<!--
  Password vault unlock panel.

  Usage:
  VaultView renders this component before a vault token exists. It emits setup
  or unlock requests without touching global application login state.
-->
<script setup lang="ts">
import { ref } from 'vue'

defineOptions({ name: 'VaultUnlockPanel' })

defineProps<{
  configured: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  unlock: [password: string]
  setup: [password: string]
}>()

const password = ref('')
const confirmPassword = ref('')
const localError = ref('')

function submit() {
  localError.value = ''
  if (password.value.length < 8) {
    localError.value = '主密码至少 8 位'
    return
  }
  emit('unlock', password.value)
}

function setup() {
  localError.value = ''
  if (password.value.length < 8) {
    localError.value = '主密码至少 8 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    localError.value = '两次输入不一致'
    return
  }
  emit('setup', password.value)
}
</script>

<template>
  <section class="unlock-panel">
    <div class="unlock-card">
      <div>
        <p class="eyebrow">你的密码库</p>
        <h2>{{ configured ? '输入主密码' : '设置主密码' }}</h2>
      </div>
      <input
        v-model="password"
        class="vault-input"
        type="password"
        autocomplete="current-password"
        placeholder="主密码"
        @keydown.enter="configured ? submit() : setup()"
      />
      <input
        v-if="!configured"
        v-model="confirmPassword"
        class="vault-input"
        type="password"
        autocomplete="new-password"
        placeholder="再次输入主密码"
        @keydown.enter="setup"
      />
      <p v-if="localError" class="error-text">{{ localError }}</p>
      <button class="primary-btn" type="button" :disabled="loading" @click="configured ? submit() : setup()">
        {{ configured ? '解锁' : '创建并解锁' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.unlock-panel {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  background: var(--color-canvas);
}

.unlock-card {
  display: grid;
  gap: 14px;
  width: min(420px, calc(100% - 32px));
  padding: 24px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

h2 {
  margin: 0;
  color: var(--color-text);
  font-size: calc(24px * var(--font-scale));
}

.vault-input {
  height: 38px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 0 14px;
  outline: 0;
}

.primary-btn {
  height: 36px;
  border: 0;
  border-radius: 999px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.error-text {
  margin: 0;
  color: var(--color-danger);
  font-size: calc(12px * var(--font-scale));
}
</style>
