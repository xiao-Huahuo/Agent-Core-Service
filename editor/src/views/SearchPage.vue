<!--
  Knowledge base search view embedded in the workspace grid.

  Usage:
  Rendered inside EditorWorkspace when mainView === 'search'.
  Initial centered state with title + large search box, transitions
  upward on submit, results scroll below.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { FileSearch, Layers, List, Loader, Search, Sparkles, ToggleLeft, ToggleRight, X } from 'lucide-vue-next'

import { highlightMatch } from '@/utils/highlight'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import SplitText from '@/components/editor_workspace/SplitText.vue'

const workspaceStore = useWorkspaceStore()
const settingsStore = useSettingsStore()

const inputEl = ref<HTMLInputElement | null>(null)
const hasSearched = ref(false)

const unifiedMode = computed({
  get: () => workspaceStore.searchUnified,
  set: (v: boolean) => { workspaceStore.searchUnified = v },
})

function baseName(uri: string): string {
  const parts = uri.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? uri
}

function onSubmit() {
  const q = workspaceStore.searchQuery.trim()
  if (!q) return
  hasSearched.value = true
  workspaceStore.performSearch(q)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    event.preventDefault()
    onSubmit()
  }
}

function openResult(path: string) {
  let node = workspaceStore.flatNodes?.find((n) => n.path === path)
  if (!node) {
    const name = baseName(path)
    node = workspaceStore.flatNodes?.find((n) => n.path.endsWith(`/${name}`) || n.name === name)
  }
  if (node) {
    workspaceStore.setMainView('editor')
    workspaceStore.selectFile(node)
  }
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

function askAgent() {
  const q = workspaceStore.searchQuery.trim()
  if (!q) return
  workspaceStore.setMainView('editor')
  workspaceStore.agentSidebarOpen = true
  workspaceStore.pendingAgentPrompt = `在知识库里面找一个文件,特征是${q}`
}

// ---- unified mode merge logic ----

interface MergedResult {
  name: string
  path: string
  filenameMatched: boolean
  fulltextSnippet: string
  semanticContent: string
}

const unifiedResults = computed<MergedResult[]>(() => {
  const r = workspaceStore.searchResults
  if (!r) return []
  const byName = new Map<string, MergedResult>()
  const ensure = (key: string, path: string): MergedResult => {
    if (!byName.has(key)) {
      byName.set(key, { name: key, path, filenameMatched: false, fulltextSnippet: '', semanticContent: '' })
    }
    return byName.get(key)!
  }
  for (const f of r.filename_results) {
    const n = baseName(f.path)
    const m = ensure(n, f.path)
    m.filenameMatched = true
  }
  for (const ft of r.fulltext_results) {
    const n = baseName(ft.source_uri)
    const m = ensure(n, ft.source_uri)
    if (ft.snippet) m.fulltextSnippet = ft.snippet
  }
  for (const s of r.semantic_results) {
    const uri = (s as Record<string, unknown>).source_uri as string
    const content = (s as Record<string, unknown>).content as string
    const n = baseName(uri)
    const m = ensure(n, uri)
    if (content) m.semanticContent = content
  }
  return [...byName.values()]
})

function syncFromStore() {
  if (workspaceStore.searchQuery.trim() && workspaceStore.searchResults) {
    hasSearched.value = true
  } else if (!workspaceStore.searchQuery.trim() && !workspaceStore.searchResults) {
    hasSearched.value = false
  }
}

watch(() => workspaceStore.mainView, (view) => {
  if (view === 'search') {
    syncFromStore()
    nextTick(() => inputEl.value?.focus())
  }
})

onMounted(() => {
  syncFromStore()
  inputEl.value?.focus()
})
</script>

<template>
  <div class="search-page" :class="{ searched: hasSearched }">
    <!-- Animating search stage (absolute, transitions top) -->
    <div class="search-stage" :class="{ pinned: hasSearched }">
      <Transition name="title-fade">
        <div v-if="!hasSearched" class="hero-title">
          <SplitText text="知识库搜索" tag="h1" :trigger-on-mount="true" />
          <p>在知识库中搜索文件、内容和语义匹配</p>
        </div>
      </Transition>

      <div class="search-box-wrap">
        <div class="search-box">
          <Search :size="20" class="search-box-icon" />
          <input
            ref="inputEl"
            v-model="workspaceStore.searchQuery"
            type="text"
            placeholder="搜索文件..."
            class="search-box-input"
            @keydown="onKeydown"
          />
          <Loader v-if="workspaceStore.searching" :size="18" class="search-box-spinner" />
          <button
            v-if="workspaceStore.searchQuery && !workspaceStore.searching"
            class="search-box-clear"
            type="button"
            @click="workspaceStore.searchQuery = ''"
          >
            <X :size="12" />
          </button>
          <button class="search-box-submit" type="button" @click="onSubmit">
            <Search :size="16" />
            <span>搜索</span>
          </button>
        </div>

        <div class="search-box-toggles">
          <button
            class="toggle-btn"
            :class="{ on: workspaceStore.fulltextEnabled }"
            type="button"
            @click="toggleFulltext"
          >
            <component :is="workspaceStore.fulltextEnabled ? ToggleRight : ToggleLeft" :size="13" class="toggle-icon" />
            <FileSearch :size="11" />
            <span>内容搜索</span>
          </button>
          <button
            class="toggle-btn"
            :class="{ on: workspaceStore.semanticEnabled }"
            type="button"
            @click="toggleSemantic"
          >
            <component :is="workspaceStore.semanticEnabled ? ToggleRight : ToggleLeft" :size="14" class="toggle-icon" />
            <span>语义搜索</span>
          </button>
          <button class="ai-search-btn" type="button" title="AI帮你搜" @click="askAgent">
            <Sparkles :size="12" />
          </button>
        </div>
      </div>
    </div>

    <!-- Results (below absolute search-stage, scrolls with page) -->
    <div v-if="hasSearched && workspaceStore.searchQuery" class="results-area">
      <div v-if="workspaceStore.searchResults" class="results-header">
        <span class="results-count">
          {{ unifiedMode ? unifiedResults.length : (workspaceStore.searchResults.filename_results.length + workspaceStore.searchResults.fulltext_results.length + workspaceStore.searchResults.semantic_results.length) }} 个结果
        </span>
        <button
          class="mode-toggle"
          type="button"
          :class="{ active: unifiedMode }"
          @click="unifiedMode = !unifiedMode"
        >
          <component :is="unifiedMode ? Layers : List" :size="12" />
          <span>{{ unifiedMode ? '联合搜索' : '搜索分离' }}</span>
        </button>
      </div>

      <div v-if="workspaceStore.searchResults" class="results-container">
        <!-- === SEPARATED MODE === -->
        <template v-if="!unifiedMode">
          <div v-if="workspaceStore.searchResults.filename_results.length" class="result-group">
            <div class="group-label">文件</div>
            <button
              v-for="item in workspaceStore.searchResults.filename_results"
              :key="item.path"
              class="result-card"
              type="button"
              @click="openResult(item.path)"
            >
              <div class="card-title">
                <span class="card-name" v-html="highlightMatch(item.name, workspaceStore.searchQuery)" />
              </div>
              <div class="card-path">{{ item.path }}</div>
            </button>
          </div>

          <div v-if="workspaceStore.searchResults.fulltext_results.length" class="result-group">
            <div class="group-label">内容匹配</div>
            <button
              v-for="item in workspaceStore.searchResults.fulltext_results"
              :key="item.source_uri"
              class="result-card"
              type="button"
              @click="openResult(item.source_uri)"
            >
              <div class="card-title">
                <span class="card-name">{{ baseName(item.source_uri) }}</span>
              </div>
              <div class="card-snippet" v-html="highlightMatch(item.snippet, workspaceStore.searchQuery)" />
              <div class="card-path">{{ item.source_uri }}</div>
            </button>
          </div>

          <div v-if="workspaceStore.searchResults.semantic_results.length" class="result-group">
            <div class="group-label">语义匹配</div>
            <button
              v-for="item in workspaceStore.searchResults.semantic_results"
              :key="(item as Record<string, unknown>).memory_id as string"
              class="result-card"
              type="button"
              @click="openResult((item as Record<string, unknown>).source_uri as string)"
            >
              <div class="card-title">
                <span class="card-name">{{ baseName((item as Record<string, unknown>).source_uri as string) }}</span>
                <span class="semantic-tag">语义</span>
              </div>
              <div class="card-snippet">{{ (item as Record<string, unknown>).content }}</div>
              <div class="card-path">{{ (item as Record<string, unknown>).source_uri }}</div>
            </button>
          </div>
        </template>

        <!-- === UNIFIED MODE === -->
        <template v-else>
          <button
            v-for="item in unifiedResults"
            :key="item.path"
            class="result-card"
            type="button"
            @click="openResult(item.path)"
          >
            <div class="card-title">
              <span class="card-name" v-html="highlightMatch(item.name, workspaceStore.searchQuery)" />
              <span v-if="item.semanticContent" class="semantic-tag">语义</span>
            </div>
            <div
              v-if="item.fulltextSnippet"
              class="card-snippet"
              v-html="highlightMatch(item.fulltextSnippet, workspaceStore.searchQuery)"
            />
            <div v-else-if="item.semanticContent" class="card-snippet-truncated">{{ item.semanticContent.slice(0, 200) }}</div>
            <div class="card-path">{{ item.path }}</div>
          </button>
        </template>
      </div>

      <div v-else-if="!workspaceStore.searching" class="results-empty">
        无匹配结果
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  position: relative;
  height: 100%;
  overflow-y: auto;
  background: var(--color-canvas);
}

/* ---- Animated search stage (absolute, transitions top) ---- */
.search-stage {
  position: absolute;
  left: 50%;
  top: 35%;
  transform: translateX(-50%);
  width: min(88%, 620px);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: top 350ms cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.search-stage.pinned {
  top: 16px;
}

.hero-title {
  text-align: center;
  margin-bottom: 28px;
  pointer-events: none;
}

.hero-title h1 {
  margin: 0;
  color: var(--color-text);
  font-family: "Monocraft", var(--font-code);
  font-size: 32px;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.hero-title p {
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.title-fade-leave-active {
  transition:
    opacity 250ms ease,
    transform 250ms ease;
}

.title-fade-leave-to {
  opacity: 0;
  transform: translateY(-14px);
}

/* ---- Search box ---- */
.search-box-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 48px;
  padding: 0 4px 0 18px;
  border: 2px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

:root[data-theme="dark"] .search-box {
  background: #1c1c20;
  border-color: #2a2a30;
}

:root[data-theme="light"] .search-box {
  background: #f4f4f8;
  border-color: #dcdce4;
}

.search-box:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.search-box-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.search-box-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: 15px;
}

.search-box-input::placeholder {
  color: var(--color-text-muted);
}

.search-box-spinner {
  flex-shrink: 0;
  color: var(--color-primary);
  animation: spin 700ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.search-box-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border: 0;
  border-radius: 999px;
  background: var(--color-border);
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
}

.search-box-clear:hover {
  background: var(--color-border-strong);
  color: var(--color-text);
}

.search-box-submit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 20px;
  border: 0;
  border-radius: 999px;
  background: var(--color-primary);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-fast);
}

.search-box-submit:hover {
  background: var(--color-primary-hover);
}

/* Toggles */
.search-box-toggles {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
}

.toggle-btn.on {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.toggle-icon {
  margin-left: -3px;
}

.ai-search-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid var(--color-accent);
  border-radius: 999px;
  background: transparent;
  color: var(--color-accent);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.ai-search-btn:hover {
  background: rgba(235, 36, 99, 0.12);
}

/* ---- Results (normal flow, scrolls with page) ---- */
.results-area {
  margin-top: 140px;
  padding: 0 24px 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: min(90%, 720px);
  margin-bottom: 16px;
}

.results-count {
  color: var(--color-text-muted);
  font-size: 12px;
}

.mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
}

.mode-toggle.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.results-container {
  width: min(90%, 720px);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.results-empty {
  width: min(90%, 720px);
  text-align: center;
  padding: 60px 0;
  color: var(--color-text-muted);
  font-size: 14px;
}

/* Result groups (separated mode) */
.result-group {
  margin-bottom: 16px;
}

.group-label {
  padding: 6px 12px;
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Result card */
.result-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding: 10px 14px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease;
}

.result-card:hover {
  background: var(--color-surface-active);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-name {
  font-size: 15px;
  font-weight: 650;
  color: var(--color-text);
}

.card-name :deep(mark) {
  background: rgba(255, 196, 0, 0.35);
  color: inherit;
  border-radius: 2px;
}

.card-snippet {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-snippet :deep(mark) {
  background: rgba(255, 196, 0, 0.35);
  color: inherit;
  border-radius: 2px;
}

.card-snippet-truncated {
  font-size: 13px;
  color: var(--color-text-muted);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-path {
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-code);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.semantic-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(235, 36, 99, 0.12);
  color: var(--color-accent);
  font-size: 10px;
  font-weight: 600;
}
</style>
