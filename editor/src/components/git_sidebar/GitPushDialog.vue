<!--
  Git push dialog.

  Usage:
  Shows local-to-remote mapping, independently scrollable unpushed previews,
  explicit target-creation dialogs, and safe force-with-lease retry handling.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronRight, X } from 'lucide-vue-next'

import GitPushFileTree from '@/components/git_sidebar/GitPushFileTree.vue'
import GitPushTargetCreateDialog from '@/components/git_sidebar/GitPushTargetCreateDialog.vue'
import { buildGitPushTree } from '@/components/git_sidebar/gitPushTree'
import { useGitStore } from '@/stores/git'

defineOptions({ name: 'GitPushDialog' })

type CreateTargetMode = 'local' | 'remote' | 'remote-branch'

const CREATE_LOCAL_VALUE = '__create_local__'
const CREATE_REMOTE_VALUE = '__create_remote__'
const CREATE_REMOTE_BRANCH_VALUE = '__create_remote_branch__'

const gitStore = useGitStore()
const localBranch = ref('')
const remote = ref('')
const remoteBranch = ref('')
const pushError = ref('')
const pushScope = ref<'current' | 'all'>('current')
const createTargetMode = ref<CreateTargetMode | null>(null)

const localBranches = computed(() => gitStore.status.branches.map((item) => item.name))
const canSubmit = computed(() => (
  Boolean(remote.value)
  && (
    pushScope.value === 'all'
    || (Boolean(localBranch.value) && Boolean(remoteBranch.value))
  )
))
const unpushedFileTree = computed(() => buildGitPushTree(gitStore.history.unpushed_files))
const remoteBranchOptions = computed(() => {
  const prefix = `${remote.value}/`
  const fromRemote = gitStore.status.remote_branches
    .filter((item) => item.startsWith(prefix))
    .map((item) => item.slice(prefix.length))
  return [...new Set([...fromRemote, ...localBranches.value])]
})
const createDialogExistingNames = computed(() => {
  if (createTargetMode.value === 'local') return localBranches.value
  if (createTargetMode.value === 'remote') return gitStore.status.remotes
  return remoteBranchOptions.value
})

watch(
  () => gitStore.pushOpen,
  (open) => {
    if (!open) return
    localBranch.value = gitStore.status.current_branch || localBranches.value[0] || ''
    remote.value = gitStore.status.remotes[0] || ''
    const upstreamBranch = gitStore.status.upstream.includes('/')
      ? gitStore.status.upstream.split('/').slice(1).join('/')
      : ''
    remoteBranch.value = upstreamBranch || localBranch.value
    pushError.value = ''
    pushScope.value = 'current'
    createTargetMode.value = null
  },
)

/** Open a dedicated creation dialog when a sentinel dropdown option is selected. */
function handleLocalSelection(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (value === CREATE_LOCAL_VALUE) createTargetMode.value = 'local'
  else localBranch.value = value
}

/** Select an existing remote or open the named-remote creation dialog. */
function handleRemoteSelection(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (value === CREATE_REMOTE_VALUE) {
    createTargetMode.value = 'remote'
    return
  }
  remote.value = value
}

/** Select an existing destination branch or open its explicit creation dialog. */
function handleRemoteBranchSelection(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (value === CREATE_REMOTE_BRANCH_VALUE) createTargetMode.value = 'remote-branch'
  else remoteBranch.value = value
}

/** Apply a name returned by the target creation dialog to the corresponding dropdown. */
function handleTargetCreated(name: string): void {
  if (createTargetMode.value === 'local') {
    localBranch.value = name
  } else if (createTargetMode.value === 'remote') {
    remote.value = name
  } else {
    remoteBranch.value = name
  }
  createTargetMode.value = null
}

/** Return whether a rejected normal push is eligible for an explicit lease-protected retry. */
function canRetryWithLease(message: string): boolean {
  return /non-fast-forward|fetch first|rejected|stale info|非快进|拒绝/i.test(message)
}

/** Push the selected mapping and offer force-with-lease only for remote-history rejection. */
async function submitPush(): Promise<void> {
  if (!canSubmit.value) {
    pushError.value = '请先选择本地分支、远程仓库和远程分支。'
    return
  }
  pushError.value = ''
  try {
    await gitStore.push({
      localBranch: localBranch.value,
      remote: remote.value,
      remoteBranch: remoteBranch.value,
      allBranches: pushScope.value === 'all',
    })
  } catch (error) {
    pushError.value = error instanceof Error ? error.message : '推送失败'
    if (!canRetryWithLease(pushError.value)) return
    const confirmed = window.confirm(
      '普通推送失败。是否使用 force-with-lease 重试？这可能覆盖远端提交，但会在远端已变化时拒绝执行。',
    )
    if (!confirmed) return
    try {
      await gitStore.push({
        localBranch: localBranch.value,
        remote: remote.value,
        remoteBranch: remoteBranch.value,
        forceWithLease: true,
        allBranches: pushScope.value === 'all',
      })
    } catch (forceError) {
      pushError.value = forceError instanceof Error ? forceError.message : '强制推送失败'
    }
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="dialog-backdrop" role="presentation" @click.self="gitStore.pushOpen = false">
      <section class="push-dialog" role="dialog" aria-modal="true" aria-labelledby="git-push-title">
        <header>
          <div>
            <h2 id="git-push-title">推送提交</h2>
            <p v-if="pushScope === 'all'">全部本地分支 → {{ remote || '未选择' }}</p>
            <p v-else>
              {{ localBranch || '未选择' }} → {{ remote || '未选择' }}:{{ remoteBranch || '未选择' }}
            </p>
          </div>
          <button type="button" aria-label="关闭" @click="gitStore.pushOpen = false">
            <X :size="16" />
          </button>
        </header>

        <div class="push-mapping">
          <label>
            <span>本地分支</span>
            <select
              :value="localBranch"
              :disabled="pushScope === 'all'"
              @change="handleLocalSelection"
            >
              <option value="" disabled>选择本地分支</option>
              <option v-for="branch in localBranches" :key="branch" :value="branch">
                {{ branch }}
              </option>
              <option :value="CREATE_LOCAL_VALUE">新建本地分支…</option>
            </select>
          </label>
          <ChevronRight :size="16" />
          <label>
            <span>远程仓库</span>
            <select :value="remote" @change="handleRemoteSelection">
              <option value="" disabled>选择远程仓库</option>
              <option v-for="item in gitStore.status.remotes" :key="item" :value="item">
                {{ item }}
              </option>
              <option :value="CREATE_REMOTE_VALUE">新建远程仓库…</option>
            </select>
          </label>
          <label>
            <span>远程分支</span>
            <select
              :value="remoteBranch"
              :disabled="pushScope === 'all'"
              @change="handleRemoteBranchSelection"
            >
              <option value="" disabled>选择远程分支</option>
              <option v-for="branch in remoteBranchOptions" :key="branch" :value="branch">
                {{ branch }}
              </option>
              <option :value="CREATE_REMOTE_BRANCH_VALUE">新建远程分支…</option>
            </select>
          </label>
        </div>

        <div class="push-content">
          <section>
            <h3>未推送提交</h3>
            <ul class="scroll-region">
              <li v-for="commit in gitStore.history.unpushed_commits" :key="commit.hash">
                <span>{{ commit.summary }}</span>
                <code>{{ commit.short_hash }}</code>
              </li>
              <li v-if="gitStore.history.unpushed_commits.length === 0" class="empty">
                没有未推送提交
              </li>
            </ul>
          </section>
          <section>
            <h3>未推送文件</h3>
            <div class="scroll-region">
              <GitPushFileTree v-if="unpushedFileTree.length > 0" :nodes="unpushedFileTree" />
              <p v-else class="empty">没有未推送文件</p>
            </div>
          </section>
        </div>

        <p v-if="pushError" class="push-error" role="alert">{{ pushError }}</p>
        <footer>
          <label class="push-scope">
            <span>推送范围</span>
            <select v-model="pushScope">
              <option value="current">当前分支</option>
              <option value="all">所有本地分支</option>
            </select>
          </label>
          <div>
            <button class="secondary" type="button" @click="gitStore.pushOpen = false">取消</button>
            <button
              class="primary"
              type="button"
              :disabled="gitStore.mutating || !canSubmit"
              @click="submitPush"
            >
              推送
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>

  <GitPushTargetCreateDialog
    v-if="createTargetMode"
    :mode="createTargetMode"
    :existing-names="createDialogExistingNames"
    @close="createTargetMode = null"
    @created="handleTargetCreated"
  />
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-24);
  background: rgba(6, 9, 16, 0.66);
}

.push-dialog {
  display: flex;
  flex-direction: column;
  width: min(900px, 94vw);
  height: min(680px, 88vh);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
}

header,
footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-16);
  padding: var(--space-16);
}

header {
  border-bottom: 1px solid var(--color-border);
}

footer {
  border-top: 1px solid var(--color-border);
}

h2,
h3,
p {
  margin: 0;
}

h2 {
  color: var(--color-text);
  font-size: var(--font-size-md);
}

h3 {
  margin-bottom: var(--space-8);
  color: var(--color-text);
  font-size: var(--font-size-sm);
}

header p,
.push-scope {
  margin-top: var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

header button {
  padding: var(--space-4);
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.push-mapping {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: minmax(150px, 1fr) auto minmax(130px, .7fr) minmax(150px, 1fr);
  align-items: end;
  gap: var(--space-12);
  padding: var(--space-16);
  border-bottom: 1px solid var(--color-border);
}

label {
  display: grid;
  gap: var(--space-4);
  color: var(--color-text-muted);
  font: inherit;
}

select {
  height: 32px;
  min-width: 0;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
}

select:focus {
  border-color: var(--color-primary);
}

.push-content {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  min-height: 0;
  overflow: hidden;
}

.push-content section {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  padding: var(--space-16);
  overflow: hidden;
}

.push-content section + section {
  border-left: 1px solid var(--color-border);
}

.scroll-region {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0;
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

ul {
  list-style: none;
}

li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-8);
  padding: var(--space-8) 0;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font: inherit;
}

li span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

code {
  color: var(--color-text-muted);
  font: inherit;
}

.empty {
  display: block;
  color: var(--color-text-muted);
}

.push-error {
  flex: 0 0 auto;
  padding: var(--space-8) var(--space-16);
  border-top: 1px solid var(--color-border);
  color: var(--color-danger);
  font: inherit;
}

.push-scope {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.push-scope select {
  min-width: 126px;
}

footer div {
  display: flex;
  gap: var(--space-8);
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

@media (max-width: 720px) {
  .push-dialog {
    height: min(760px, 92vh);
  }

  .push-mapping {
    grid-template-columns: 1fr;
  }

  .push-mapping > svg {
    display: none;
  }

  .push-content {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  }

  .push-content section + section {
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }
}
</style>
