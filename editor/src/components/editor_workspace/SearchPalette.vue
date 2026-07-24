<!--
  Inline search bar + dropdown results.

  Usage:
  Embedded in TopCommandBar header center. Always shows a search input;
  when focused and a query is present, a dropdown results panel appears
  below with filename / fulltext / semantic results grouped by <hr>.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Clock, FileSearch, Loader, Search, Sparkles, Trash2, X } from 'lucide-vue-next'

import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()

const inputEl = ref<HTMLInputElement | null>(null)
const wrapperEl = ref<HTMLElement | null>(null)
const focused = ref(false)

const showDropdown = computed(() => focused.value)

function handleClickOutside(event: MouseEvent) {
  if (wrapperEl.value && !wrapperEl.value.contains(event.target as Node)) {
    focused.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleClickOutside)
})

function selectHistory(query: string) {
  workspaceStore.searchQuery = query
  workspaceStore.performSearch(query)
  inputEl.value?.focus()
}

watch(() => workspaceStore.searchOpen, (open) => {
  if (open) {
    nextTick(() => inputEl.value?.focus())
  }
})

function onFocus() {
  focused.value = true
}

function handleOpenFile(path: string) {
  let node = workspaceStore.flatNodes?.find((n) => n.path === path)
  if (!node) {
    const name = baseName(path)
    node = workspaceStore.flatNodes?.find((n) => n.path.endsWith(`/${name}`) || n.name === name)
  }
  if (node) {
    workspaceStore.selectFile(node)
  }
  workspaceStore.closeSearch()
}

function toggleFulltext() {
  workspaceStore.fulltextEnabled = !workspaceStore.fulltextEnabled
  if (workspaceStore.searchQuery.trim()) {
    workspaceStore.performSearch(workspaceStore.searchQuery)
  }
}

function toggleSemantic() {
  workspaceStore.semanticEnabled = !workspaceStore.semanticEnabled
  if (workspaceStore.searchQuery.trim()) {
    workspaceStore.performSearch(workspaceStore.searchQuery)
  }
}

function clearQuery() {
  workspaceStore.searchQuery = ''
  inputEl.value?.focus()
}

function baseName(uri: string): string {
  const parts = uri.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? uri
}

function askAgentSearch() {
  const q = workspaceStore.searchQuery.trim()
  if (!q) return
  workspaceStore.agentSidebarOpen = true
  workspaceStore.pendingAgentPrompt = `在知识库里找一个文件，特征是：${q}`
}

function navigateToSearchPage() {
  workspaceStore.searchQuery = workspaceStore.searchQuery.trim()
  workspaceStore.setMainView('search')
  focused.value = false
}

</script>

<template>
  <div ref="wrapperEl" class="search-wrapper" :class="{ focused: focused }">
    <div class="search-bar">
      <Search :size="16" class="search-icon" />
      <input
        ref="inputEl"
        v-model="workspaceStore.searchQuery"
        type="text"
        placeholder="搜索文件..."
        class="search-input"
        @focus="onFocus"
      />
      <Loader v-if="workspaceStore.searching" :size="14" class="spinner" />
      <button
        v-if="workspaceStore.searchQuery && !workspaceStore.searching"
        class="clear-btn"
        type="button"
        @click="clearQuery"
      >
        <X :size="12" />
      </button>
      <button
        class="search-submit-btn"
        type="button"
        @mousedown.prevent="navigateToSearchPage"
      >
        <Search :size="12" class="submit-icon" />
        <span class="submit-label">Search</span>
      </button>
    </div>

    <!-- Dropdown results -->
    <Transition name="dropdown">
      <div v-if="showDropdown" class="search-dropdown">
        <!-- Toggle row: always visible -->
        <div class="toggle-row">
          <button
            class="toggle-btn"
            :class="{ on: workspaceStore.fulltextEnabled }"
            type="button"
            @mousedown.prevent="toggleFulltext"
          >
            <div class="toggle-inner">
              <div class="toggle-dot"></div>
              <span class="toggle-label">内容搜索</span>
            </div>
            <div class="toggle-overlay">
              <div class="toggle-overlay-inner">
                <FileSearch :size="12" />
                <span>内容搜索</span>
                <svg xmlns="http://www.w3.org/2000/svg" class="toggle-arrow" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 12h14"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 6l6 6-6 6"></path>
                </svg>
              </div>
            </div>
          </button>
          <button
            class="toggle-btn"
            :class="{ on: workspaceStore.semanticEnabled }"
            type="button"
            @mousedown.prevent="toggleSemantic"
          >
            <div class="toggle-inner">
              <div class="toggle-dot"></div>
              <span class="toggle-label">语义搜索</span>
            </div>
            <div class="toggle-overlay">
              <div class="toggle-overlay-inner">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
                <span>语义搜索</span>
                <svg xmlns="http://www.w3.org/2000/svg" class="toggle-arrow" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 12h14"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 6l6 6-6 6"></path>
                </svg>
              </div>
            </div>
          </button>
          <button
            class="ai-search-btn"
            type="button"
            title="AI 帮你搜索"
            @mousedown.prevent="askAgentSearch"
          >
            <Sparkles :size="12" />
          </button>
        </div>

        <!-- History: no query, has history -->
        <template v-if="!workspaceStore.searchQuery && workspaceStore.searchHistory.length">
          <div class="result-list">
            <div class="history-header">
              <span class="group-label">最近搜索</span>
              <button class="history-clear-btn" type="button" title="清除历史" @mousedown.prevent="workspaceStore.clearSearchHistory()">
                <Trash2 :size="11" />
              </button>
            </div>
            <button
              v-for="item in workspaceStore.searchHistory"
              :key="item"
              class="result-row history-row"
              type="button"
              @mousedown.prevent="selectHistory(item)"
            >
              <Clock :size="12" class="history-icon" />
              <span class="history-text">{{ item }}</span>
            </button>
          </div>
        </template>

        <!-- Search mode: has query -->
        <template v-if="workspaceStore.searchQuery">
          <!-- Results -->
          <div v-if="workspaceStore.searchResults" class="result-list">
            <!-- Filename results -->
            <div v-if="workspaceStore.searchResults.filename_results.length" class="result-group">
              <div class="group-label">文件</div>
              <button
                v-for="item in workspaceStore.searchResults.filename_results"
                :key="item.path"
                class="result-row"
                type="button"
                @mousedown.prevent="handleOpenFile(item.path)"
              >
                <span class="result-name">{{ item.name }}</span>
              </button>
            </div>

            <hr v-if="workspaceStore.searchResults.filename_results.length && workspaceStore.searchResults.fulltext_results.length" />

            <!-- Full-text results -->
            <div v-if="workspaceStore.searchResults.fulltext_results.length" class="result-group">
              <div class="group-label">内容匹配</div>
              <button
                v-for="item in workspaceStore.searchResults.fulltext_results"
                :key="item.source_uri"
                class="result-row"
                type="button"
                @mousedown.prevent="handleOpenFile(item.source_uri)"
              >
                <span class="result-name">{{ baseName(item.source_uri) }}</span>
                <span class="result-meta">{{ item.snippet }}</span>
              </button>
            </div>

            <hr v-if="(workspaceStore.searchResults.filename_results.length || workspaceStore.searchResults.fulltext_results.length) && workspaceStore.searchResults.semantic_results.length" />

            <!-- Semantic results -->
            <div v-if="workspaceStore.searchResults.semantic_results.length" class="result-group">
              <div class="group-label">语义匹配</div>
              <button
                v-for="item in workspaceStore.searchResults.semantic_results"
                :key="(item as Record<string, unknown>).memory_id as string"
                class="result-row"
                type="button"
                @mousedown.prevent="handleOpenFile((item as Record<string, unknown>).source_uri as string)"
              >
                <span class="result-name">{{ baseName((item as Record<string, unknown>).source_uri as string) }}</span>
                <span class="result-meta">{{ (item as Record<string, unknown>).content }}</span>
              </button>
            </div>
          </div>
          <div v-else-if="!workspaceStore.searching" class="result-list empty-state">
            无匹配结果
          </div>
        </template>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.search-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  max-width: 560px;
  width: 100%;
  margin: 2px 0;
  z-index: 100;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  height: 26px;
  padding: 0 1px 0 var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  transition: border-color var(--transition-fast);
}

:root[data-theme="dark"] .search-bar {
  background: #1c1c20;
  border-color: #2a2a30;
}

:root[data-theme="light"] .search-bar {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.search-wrapper.focused .search-bar {
  border-color: var(--color-primary);
}

.search-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

:root[data-theme="dark"] .search-input::placeholder {
  color: #6b6b78;
}

:root[data-theme="light"] .search-input::placeholder {
  color: #9393a0;
}

.spinner {
  flex-shrink: 0;
  color: var(--color-primary);
  animation: spin 700ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.clear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 0;
  border-radius: 999px;
  background: var(--color-border);
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
}

.clear-btn:hover {
  background: var(--color-border-strong);
  color: var(--color-text);
}

.search-submit-btn {
  position: relative;
  height: 22px;
  width: 22px;
  padding: 0 0 0 22px;
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  font-size: calc(11px * var(--font-scale));
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  overflow: hidden;
  white-space: nowrap;
  line-height: 22px;
  transition: color 0.3s 0.1s ease-out;
  outline: none;
  text-align: center;
}

.search-submit-btn::before {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  margin: auto;
  content: "";
  border-radius: 50%;
  display: block;
  width: 20em;
  height: 20em;
  left: -5em;
  text-align: center;
  transition: box-shadow 0.5s ease-out;
  z-index: -1;
}

.submit-icon {
  position: absolute;
  left: 5px;
  top: 50%;
  transform: translateY(-50%);
}

.submit-label {
  opacity: 0;
  transition: opacity 180ms ease;
}

.search-submit-btn:hover {
  color: #fff;
  border-color: var(--color-primary);
}

.search-submit-btn:hover::before {
  box-shadow: inset 0 0 0 10em var(--color-primary);
}

.search-submit-btn:hover .submit-label {
  opacity: 1;
}

/* Dropdown */
.search-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 100;
  max-height: 360px;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

:root[data-theme="dark"] .search-dropdown {
  background: #1c1c20;
  border-color: #2a2a30;
}

:root[data-theme="light"] .search-dropdown {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-6) var(--space-10);
  border-bottom: 1px solid var(--color-border);
}

.toggle-btn {
  position: relative;
  cursor: pointer;
  overflow: hidden;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: transparent;
  padding: 0;
  font-size: calc(11px * var(--font-scale));
  font-weight: 500;
  font-family: var(--font-ui);
  color: var(--color-text-muted);
  box-shadow: none;
  transition: all 0.3s;
  outline: none;
}

.toggle-btn .toggle-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 12px;
  transition: all 0.3s;
}

.toggle-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-muted);
  transition: all 0.3s;
}

.toggle-label {
  transition: all 0.3s;
  white-space: nowrap;
}

.toggle-overlay {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
  display: flex;
  height: 100%;
  width: 100%;
  transform: translateX(100%);
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--color-primary);
  color: #fff;
  opacity: 0;
  transition: all 0.3s;
}

.toggle-overlay-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  padding: 2px 12px;
}

.toggle-overlay-inner span {
  font-size: calc(11px * var(--font-scale));
  font-weight: 500;
  line-height: 1;
}

.toggle-arrow {
  width: 12px;
  height: 12px;
  line-height: 1;
}

/* Off state hover: overlay fades in, inner fades out */
.toggle-btn:not(.on):hover .toggle-inner {
  opacity: 0;
}

.toggle-btn:not(.on):hover .toggle-overlay {
  transform: translateX(0);
  opacity: 1;
}

.toggle-btn:not(.on):hover {
  border-color: var(--color-primary);
}

/* On state: primary border + dot */
.toggle-btn.on {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.toggle-btn.on .toggle-dot {
  background: var(--color-primary);
}

/* On state hover: overlay fades in, inner fades out */
.toggle-btn.on:hover .toggle-inner {
  opacity: 0;
}

.toggle-btn.on:hover .toggle-overlay {
  transform: translateX(0);
  opacity: 1;
}

.ai-search-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 1px solid var(--color-accent);
  border-radius: 999px;
  background: transparent;
  color: var(--color-accent);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast);
}

.ai-search-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background: rgba(235, 36, 99, 0.12);
}

.result-list {
  max-height: 300px;
  overflow: auto;
  padding: var(--space-6);
}

.result-group {
  padding: var(--space-2) 0;
}

.group-label {
  padding: var(--space-4) var(--space-8);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-6) var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.result-row:hover {
  background: var(--color-surface-active);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-8);
}

.history-clear-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.history-clear-btn:hover {
  background: var(--color-surface-active);
  color: var(--color-text);
}

.history-row {
  align-items: center;
  gap: var(--space-8);
}

.history-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.history-text {
  font-size: calc(13px * var(--font-scale));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-name {
  font-size: calc(13px * var(--font-scale));
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-meta {
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

hr {
  margin: var(--space-4) var(--space-6);
  border: 0;
  border-top: 1px solid var(--color-border);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-20);
  color: var(--color-text-muted);
  font-size: calc(13px * var(--font-scale));
}

/* Transition */
.dropdown-enter-active {
  transition: opacity 120ms ease, transform 120ms ease;
}

.dropdown-leave-active {
  transition: opacity 100ms ease, transform 100ms ease;
}

.dropdown-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
