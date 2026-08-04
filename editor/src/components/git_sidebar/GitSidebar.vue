<!--
  Git source-control sidebar.

  Usage:
  The same component can be mounted in the left file column or right utility
  column. Repository state and selection remain synchronized through GitStore.
-->
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import GitChangeGroup from '@/components/git_sidebar/GitChangeGroup.vue'
import GitHistoryDropdown from '@/components/git_sidebar/GitHistoryDropdown.vue'
import GitPushDialog from '@/components/git_sidebar/GitPushDialog.vue'
import { useGitStore } from '@/stores/git'

defineOptions({ name: 'GitSidebar' })

const gitStore = useGitStore()
let refreshTimer: number | null = null

function scheduleRefresh(): void {
  if (refreshTimer !== null) window.clearTimeout(refreshTimer)
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null
    void gitStore.refresh()
  }, 180)
}

onMounted(() => {
  window.addEventListener('metaweave-knowledge-file-change', scheduleRefresh)
  void gitStore.refresh()
})

onUnmounted(() => {
  window.removeEventListener('metaweave-knowledge-file-change', scheduleRefresh)
  if (refreshTimer !== null) window.clearTimeout(refreshTimer)
})

async function restoreSelected(): Promise<void> {
  if (gitStore.selectedCount === 0) return
  const confirmed = window.confirm(
    '确定回滚选中文件吗？已跟踪文件将恢复到 HEAD；未跟踪文件会移入最近删除。',
  )
  if (!confirmed) return
  await gitStore.restoreSelected().catch(() => undefined)
}

async function commitAndOpenPush(): Promise<void> {
  await gitStore.commitSelected()
  await gitStore.openPush()
}

async function toggleHistoryDropdown(): Promise<void> {
  /** Toggle the anchored history list and load commits only when opening it. */

  if (gitStore.historyOpen) {
    gitStore.historyOpen = false
    return
  }
  await gitStore.openHistory()
}
</script>

<template>
  <aside class="git-sidebar" aria-label="Git 版本控制">
    <header class="git-header">
      <div class="git-title">
        <IcIcon name="git" :size="15" />
        <strong>Git</strong>
        <span v-if="gitStore.status.initialized">{{ gitStore.status.current_branch || 'DETACHED' }}</span>
      </div>
      <div class="git-actions">
        <button
          type="button"
          title="刷新"
          aria-label="刷新 Git 状态"
          :disabled="gitStore.loading"
          @click="gitStore.refresh"
        >
          <IcIcon name="refresh" :size="14" :class="{ spinning: gitStore.loading }" />
        </button>
        <button
          type="button"
          title="回滚选中"
          aria-label="回滚选中文件"
          :disabled="gitStore.selectedCount === 0 || gitStore.mutating"
          @click="restoreSelected"
        >
          <IcIcon name="replay" :size="14" />
        </button>
        <button type="button" title="全部展开" aria-label="全部展开" @click="gitStore.expandAll">
          <IcIcon name="unfold" :size="14" />
        </button>
        <button type="button" title="全部收缩" aria-label="全部收缩" @click="gitStore.collapseAll">
          <IcIcon name="unfold-less" :size="14" />
        </button>
      </div>
    </header>

    <div v-if="gitStore.errorMessage" class="git-error" role="alert">
      {{ gitStore.errorMessage }}
    </div>

    <div v-if="!gitStore.status.initialized" class="git-empty">
      <button
        class="init-button"
        type="button"
        :disabled="gitStore.mutating"
        @click="gitStore.initialize().catch(() => undefined)"
      >
        <IcIcon name="add" :size="34" />
        <span>创建 Git 仓库</span>
        <small>在当前知识库根目录执行 git init</small>
      </button>
    </div>

    <div v-else class="git-ready">
      <div class="git-groups">
        <GitChangeGroup
          title="更改"
          :files="gitStore.status.changes"
          :expanded="gitStore.changesExpanded"
          :selected-paths="gitStore.selectedPaths"
          @toggle-expanded="gitStore.changesExpanded = !gitStore.changesExpanded"
          @toggle-all="gitStore.setGroupSelection(gitStore.status.changes, $event)"
          @toggle-path="gitStore.togglePath"
        />
        <GitChangeGroup
          title="未进行版本管理的文件"
          :files="gitStore.status.untracked"
          :expanded="gitStore.untrackedExpanded"
          :selected-paths="gitStore.selectedPaths"
          @toggle-expanded="gitStore.untrackedExpanded = !gitStore.untrackedExpanded"
          @toggle-all="gitStore.setGroupSelection(gitStore.status.untracked, $event)"
          @toggle-path="gitStore.togglePath"
        />
        <p v-if="!gitStore.status.has_changes" class="clean-state">工作区没有更改</p>
      </div>

      <footer class="commit-panel">
        <div class="commit-toolbar">
          <div class="history-control">
            <button
              class="history-button"
              type="button"
              :aria-expanded="gitStore.historyOpen"
              aria-haspopup="listbox"
              @click="toggleHistoryDropdown().catch(() => undefined)"
            >
              <IcIcon name="history" :size="13" />
              历史提交记录
            </button>
            <GitHistoryDropdown v-if="gitStore.historyOpen" />
          </div>
          <label class="branch-switcher">
            <span class="sr-only">切换本地分支</span>
            <select
              :value="gitStore.status.current_branch"
              :disabled="gitStore.mutating || gitStore.status.detached || gitStore.status.branches.length === 0"
              aria-label="切换本地分支"
              @change="gitStore.switchBranch(($event.target as HTMLSelectElement).value).catch(() => undefined)"
            >
              <option
                v-for="branch in gitStore.status.branches"
                :key="branch.name"
                :value="branch.name"
              >
                {{ branch.name }}
              </option>
            </select>
          </label>
        </div>
        <label>
          <span class="sr-only">提交概要</span>
          <textarea
            v-model="gitStore.commitMessage"
            rows="3"
            placeholder="输入提交概要"
            maxlength="500"
          />
        </label>
        <div class="commit-actions">
          <button
            class="primary"
            type="button"
            :disabled="gitStore.selectedCount === 0 || !gitStore.commitMessage.trim() || gitStore.mutating"
            @click="gitStore.commitSelected().catch(() => undefined)"
          >
            提交
          </button>
          <button
            class="secondary"
            type="button"
            :disabled="gitStore.selectedCount === 0 || !gitStore.commitMessage.trim() || gitStore.mutating"
            @click="commitAndOpenPush().catch(() => undefined)"
          >
            <IcIcon name="upload" :size="13" />
            提交并推送
          </button>
        </div>
      </footer>
    </div>

    <GitPushDialog v-if="gitStore.pushOpen" />
  </aside>
</template>

<style scoped>
.git-sidebar {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  max-height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--color-chrome-rail-bg);
  color: var(--color-text);
}

.git-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 42px;
  padding: 0 var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.git-title,
.git-actions {
  display: flex;
  align-items: center;
}

.git-title {
  min-width: 0;
  gap: var(--space-6);
}

.git-title strong {
  font-size: calc(13px * var(--font-scale));
}

.git-title span {
  overflow: hidden;
  color: var(--color-text-muted);
  font-family: var(--font-code);
  font-size: calc(10px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}

.git-actions {
  gap: 2px;
}

.git-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: border-color 160ms ease, color 160ms ease, background 160ms ease;
}

.git-actions button:hover:not(:disabled) {
  border-color: var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.git-actions button:disabled {
  cursor: not-allowed;
  opacity: .38;
}

.spinning {
  animation: git-spin 800ms linear infinite;
}

@keyframes git-spin {
  to { transform: rotate(360deg); }
}

.git-error {
  padding: var(--space-8);
  border-bottom: 1px solid var(--color-danger);
  color: var(--color-danger);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.4;
}

.git-empty {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: var(--space-24);
}

.init-button {
  display: grid;
  justify-items: center;
  gap: var(--space-8);
  padding: var(--space-24);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  transition: border-color 180ms ease, background 180ms ease, color 180ms ease;
}

.init-button:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.init-button small {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.git-ready {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  flex: 1 1 auto;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
}

.git-groups {
  min-height: 0;
  overflow: auto;
}

.clean-state {
  margin: var(--space-24) 0;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  text-align: center;
}

.commit-panel {
  position: relative;
  z-index: 4;
  min-height: 0;
  padding: var(--space-8);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.commit-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(84px, auto);
  align-items: center;
  gap: var(--space-8);
  margin-bottom: var(--space-6);
}

.history-control {
  position: relative;
  min-width: 0;
}

.history-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  cursor: pointer;
}

.history-button:hover {
  color: var(--color-primary);
}

.branch-switcher {
  min-width: 0;
}

.branch-switcher select {
  width: 100%;
  min-height: 24px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font: inherit;
  font-size: calc(10px * var(--font-scale));
  cursor: pointer;
  transition: border-color 160ms ease, color 160ms ease, background 160ms ease;
}

.branch-switcher select:hover:not(:disabled),
.branch-switcher select:focus {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.branch-switcher select:disabled {
  cursor: not-allowed;
  opacity: .48;
}

textarea {
  width: 100%;
  min-height: 58px;
  resize: vertical;
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
  font-size: calc(11px * var(--font-scale));
  line-height: 1.45;
}

textarea:focus {
  border-color: var(--color-primary);
}

.commit-actions {
  display: grid;
  grid-template-columns: .8fr 1.2fr;
  gap: var(--space-6);
  margin-top: var(--space-6);
}

.commit-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  min-height: 30px;
  border-radius: var(--radius-sm);
  font-size: calc(11px * var(--font-scale));
  cursor: pointer;
}

.commit-actions .primary {
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.commit-actions .secondary {
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary);
}

.commit-actions button:disabled {
  cursor: not-allowed;
  opacity: .45;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
