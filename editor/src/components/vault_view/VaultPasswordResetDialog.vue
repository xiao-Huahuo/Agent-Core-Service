<!-- Password vault reset dialog. Used by the settings security section. -->
<script setup lang="ts">
import { ref } from 'vue'

import FormHeightTransition from '@/components/common/FormHeightTransition.vue'
import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'VaultPasswordResetDialog' })

const props = defineProps<{ open: boolean; requireOldPassword: boolean; saving: boolean }>()
const emit = defineEmits<{ close: []; submit: [oldPassword: string, newPassword: string, confirmation: string] }>()

const oldPassword = ref('')
const newPassword = ref('')
const confirmation = ref('')

function close() {
  oldPassword.value = ''
  newPassword.value = ''
  confirmation.value = ''
  emit('close')
}

function submit() {
  emit('submit', oldPassword.value, newPassword.value, confirmation.value)
}
</script>

<template>
  <div v-if="open" class="reset-backdrop" @click.self="close">
    <form class="reset-panel" @submit.prevent="submit">
      <header><h3>{{ requireOldPassword ? '重置密码' : '重设密码库密码' }}</h3><button type="button" title="关闭" @click="close"><IcIcon name="close" :size="16" /></button></header>
      <FormHeightTransition :watch-key="requireOldPassword ? 'with-old-password' : 'without-old-password'">
        <main>
          <label v-if="requireOldPassword" class="field required"><span><IcIcon name="shield" :size="14" />旧密码</span><input class="form-input-surface" v-model="oldPassword" type="password" autocomplete="current-password" /></label>
          <label class="field required"><span><IcIcon name="shield" :size="14" />新密码</span><input class="form-input-surface" v-model="newPassword" type="password" autocomplete="new-password" /></label>
          <label class="field required"><span><IcIcon name="check" :size="14" />确认新密码</span><input class="form-input-surface" v-model="confirmation" type="password" autocomplete="new-password" /></label>
        </main>
      </FormHeightTransition>
      <footer><button type="button" @click="close">取消</button><button class="save-btn" :disabled="saving" type="submit">{{ saving ? '重设中...' : '确认重设' }}</button></footer>
    </form>
  </div>
</template>

<style scoped>
.reset-backdrop { position: fixed; inset: 0; z-index: 300; display: grid; place-items: center; background: rgba(0, 0, 0, 0.32); }
.reset-panel { width: min(460px, calc(100vw - 32px)); border: 1px solid var(--color-border); border-radius: 28px; background: var(--color-surface); font-family: var(--font-ui); font-size: calc(14px * var(--font-scale)); }
header, footer { display: flex; align-items: center; justify-content: space-between; gap: var(--space-8); padding: var(--space-10) var(--space-16); }
h3 { margin: 0; color: var(--color-text); font-size: calc(15px * var(--font-scale)); }
header button { display: grid; place-items: center; width: 28px; height: 28px; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-muted); cursor: pointer; }
header button:hover { background: var(--color-primary-softer); color: var(--color-primary); }
main { display: grid; gap: var(--space-12); padding: var(--space-12) var(--space-16) 0; }
.field { display: grid; gap: var(--space-6); color: var(--color-text-secondary); font-size: calc(12px * var(--font-scale)); }
.field > span { display: inline-flex; align-items: center; gap: 5px; }
.field.required > span::after { margin-left: 3px; color: var(--color-danger); content: '*'; }
.field input { height: 36px; border: 1px solid var(--color-border); border-radius: 999px; outline: 0; background: var(--color-canvas); color: var(--color-text); padding: 0 14px; font: inherit; font-size: calc(13px * var(--font-scale)); }
.field input:focus { border-color: var(--color-primary); }
footer { justify-content: flex-end; padding-top: var(--space-16); }
footer button { height: 32px; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface-raised); color: var(--color-text); padding: 0 var(--space-16); font: inherit; font-size: calc(13px * var(--font-scale)); cursor: pointer; }
.save-btn { border-color: var(--color-primary) !important; background: var(--color-primary) !important; color: #fff !important; }
.save-btn:disabled { cursor: default; opacity: 0.55; }
</style>
