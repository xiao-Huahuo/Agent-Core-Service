<!--
  Git push target creation dialog.

  Usage:
  Opened from the three push mapping dropdowns to create a local branch, add a
  named remote, or define a new remote branch target without free-form selects.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

import { useGitStore } from '@/stores/git'

type GitPushTargetCreateMode = 'local' | 'remote' | 'remote-branch'

defineOptions({ name: 'GitPushTargetCreateDialog' })

const props = defineProps<{
  /** Target category selected from the parent dropdown. */
  mode: GitPushTargetCreateMode
  /** Existing names that cannot be created again. */
  existingNames: string[]
}>()

const emit = defineEmits<{
  close: []
  created: [name: string]
}>()

const gitStore = useGitStore()
const name = ref('')
const url = ref('')
const errorMessage = ref('')
const submitting = ref(false)
const nameInput = ref<HTMLInputElement | null>(null)

const title = computed(() => {
  if (props.mode === 'local') return '创建本地分支'
  if (props.mode === 'remote') return '创建远程仓库'
  return '创建远程分支'
})

const nameLabel = computed(() => (props.mode === 'remote' ? '远程名称' : '分支名称'))
const requiresUrl = computed(() => props.mode === 'remote')

onMounted(() => {
  void nextTick(() => nameInput.value?.focus())
})

/** Validate the modal fields, perform persistent creation where applicable, and return the new name. */
async function submit(): Promise<void> {
  const normalizedName = name.value.trim()
  const normalizedUrl = url.value.trim()
  errorMessage.value = ''
  if (!normalizedName) {
    errorMessage.value = `${nameLabel.value}不能为空。`
    return
  }
  if (props.existingNames.includes(normalizedName)) {
    errorMessage.value = `${normalizedName} 已存在。`
    return
  }
  if (requiresUrl.value && !normalizedUrl) {
    errorMessage.value = '远程仓库地址不能为空。'
    return
  }

  submitting.value = true
  try {
    if (props.mode === 'local') {
      await gitStore.ensureLocalBranch(normalizedName)
    } else if (props.mode === 'remote') {
      await gitStore.ensureRemote(normalizedName, normalizedUrl)
    }
    emit('created', normalizedName)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="create-backdrop" role="presentation" @click.self="emit('close')">
      <section class="create-dialog" role="dialog" aria-modal="true" :aria-label="title">
        <header>
          <h3>{{ title }}</h3>
          <button type="button" aria-label="关闭创建弹窗" @click="emit('close')">
            <X :size="16" />
          </button>
        </header>

        <form @submit.prevent="submit">
          <label>
            <span>{{ nameLabel }}</span>
            <input
              ref="nameInput"
              v-model="name"
              type="text"
              :placeholder="mode === 'remote' ? '例如 origin' : '例如 feature/notes'"
              autocomplete="off"
            />
          </label>
          <label v-if="requiresUrl">
            <span>远程仓库地址</span>
            <input
              v-model="url"
              type="text"
              placeholder="https://、ssh://、git@… 或本地仓库路径"
              autocomplete="off"
            />
          </label>
          <p v-if="mode === 'remote-branch'" class="creation-note">
            新分支将作为本次推送目标，并在点击“推送”后写入远程仓库。
          </p>
          <p v-if="errorMessage" class="create-error" role="alert">{{ errorMessage }}</p>
          <footer>
            <button class="secondary" type="button" @click="emit('close')">取消</button>
            <button class="primary" type="submit" :disabled="submitting">
              {{ submitting ? '创建中…' : '创建' }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.create-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-24);
  background: rgba(6, 9, 16, 0.52);
}

.create-dialog {
  width: min(460px, 92vw);
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
}

header,
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  padding: var(--space-12) var(--space-16);
}

header {
  border-bottom: 1px solid var(--color-border);
}

h3,
p {
  margin: 0;
}

h3 {
  font-size: var(--font-size-md);
}

header button {
  padding: var(--space-4);
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

form {
  display: grid;
  gap: var(--space-12);
  padding: var(--space-16);
}

label {
  display: grid;
  gap: var(--space-6);
  color: var(--color-text-secondary);
}

input {
  width: 100%;
  height: 34px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
}

input:focus {
  border-color: var(--color-primary);
}

.creation-note {
  color: var(--color-text-muted);
  line-height: 1.45;
}

.create-error {
  color: var(--color-danger);
}

footer {
  justify-content: flex-end;
  padding: var(--space-12) 0 0;
  border-top: 1px solid var(--color-border);
}

footer button {
  min-width: 76px;
  height: 30px;
  border-radius: var(--radius-sm);
  font: inherit;
  cursor: pointer;
}

.secondary {
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
}

.primary {
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

button:disabled {
  cursor: not-allowed;
  opacity: .5;
}
</style>
