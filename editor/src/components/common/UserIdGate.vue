<!--
  Editor user id gate.

  Usage:
  Blocks the editor routes until a local user_id is entered. The value is stored
  through the settings store and will later be replaced by backend user settings.
-->
<script setup lang="ts">
import { ref } from 'vue'

import { ensureSettingsProfile } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

defineOptions({ name: 'UserIdGate' })

const settingsStore = useSettingsStore()
const draftUserId = ref('')
const errorMessage = ref('')
const loading = ref(false)

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
    <form class="gate-panel" @submit.prevent="submitUserId">
      <span class="gate-eyebrow mono">AgentService Editor</span>
      <label for="editor-user-id">user_id</label>
      <div class="input-row">
        <input
          id="editor-user-id"
          v-model="draftUserId"
          autocomplete="username"
          autofocus
          placeholder="Enter user_id"
          type="text"
        />
        <button type="submit" :disabled="!draftUserId.trim() || loading">
          {{ loading ? 'Checking' : 'Enter' }}
        </button>
      </div>
      <p v-if="errorMessage" class="gate-error">{{ errorMessage }}</p>
    </form>
  </main>
</template>

<style scoped>
.user-gate {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  background: var(--color-canvas);
  -webkit-app-region: drag;
}

.gate-panel {
  display: grid;
  gap: var(--space-10);
  width: min(360px, calc(100vw - 32px));
  padding: var(--space-16);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  -webkit-app-region: no-drag;
}

.gate-eyebrow {
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

label {
  color: var(--color-text);
  font-size: 13px;
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
  font-family: var(--font-code);
  font-size: 13px;
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
  font-size: 13px;
}

button:disabled {
  cursor: default;
  opacity: 0.42;
}

.gate-error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
  line-height: 1.5;
}
</style>
