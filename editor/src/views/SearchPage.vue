<!--
  Knowledge base search view embedded in the workspace grid.

  Usage:
  Rendered inside EditorWorkspace when mainView === 'search'.
  Initial centered state with title + large search box, transitions
  upward on submit, results scroll below.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { highlightMatch } from '@/utils/highlight'
import { useWorkspaceStore } from '@/stores/workspace'
import SearchPalette from '@/components/editor_workspace/SearchPalette.vue'
import SplitText from '@/components/editor_workspace/SplitText.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'

const workspaceStore = useWorkspaceStore()

const hasSearched = ref(false)
/** Fixed number of search results displayed on one page. */
const PAGE_SIZE = 20
/** One-based page currently displayed in the result list. */
const currentPage = ref(1)
const unifiedMode = computed({
  get: () => workspaceStore.searchUnified,
  set: (v: boolean) => {
    workspaceStore.searchUnified = v
    currentPage.value = 1
    workspaceStore.closeEditorSidebar()
  },
})

function baseName(uri: string): string {
  const parts = uri.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? uri
}

function onSubmit() {
  const q = workspaceStore.searchQuery.trim()
  if (!q) return
  hasSearched.value = true
  currentPage.value = 1
  workspaceStore.closeEditorSidebar()
  workspaceStore.performSearch(q)
}

/** Resolves search backend paths to the current knowledge-tree node. */
function resolveResultNode(path: string): KnowledgeFileNode | undefined {
  let node = workspaceStore.flatNodes?.find((n) => n.path === path)
  if (!node) {
    const name = baseName(path)
    node = workspaceStore.flatNodes?.find((n) => n.path.endsWith(`/${name}`) || n.name === name)
  }
  return node
}

/** Opens a result through the same editor sidebar pipeline used by smart-form file cells. */
async function previewResult(path: string): Promise<void> {
  const node = resolveResultNode(path)
  if (!node || node.isDir) return
  await workspaceStore.openEditorSidebar(node)
}

/** Enters the regular editor workflow after a result is double-clicked. */
function openResult(path: string) {
  const node = resolveResultNode(path)
  if (node) {
    workspaceStore.setMainView('editor')
    workspaceStore.selectFile(node)
  }
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

/** Total result count for separated mode before pagination. */
const separatedResultCount = computed(() => {
  const results = workspaceStore.searchResults
  if (!results) return 0
  return results.filename_results.length
    + results.fulltext_results.length
    + results.semantic_results.length
})

/** Total count for whichever result presentation is active. */
const displayedResultCount = computed(() => (
  unifiedMode.value ? unifiedResults.value.length : separatedResultCount.value
))

/** Number of available pages, kept at one to simplify bounded navigation. */
const totalPages = computed(() => Math.max(1, Math.ceil(displayedResultCount.value / PAGE_SIZE)))
/** Zero-based inclusive offset of the current page in the displayed sequence. */
const pageStart = computed(() => (currentPage.value - 1) * PAGE_SIZE)
/** Zero-based exclusive offset of the current page in the displayed sequence. */
const pageEnd = computed(() => pageStart.value + PAGE_SIZE)

/**
 * Slices one separated-mode group against the global page offsets.
 * Group offsets preserve the visible filename -> fulltext -> semantic order.
 */
function sliceSeparatedGroup<T>(items: T[], groupStart: number): T[] {
  const localStart = Math.max(0, pageStart.value - groupStart)
  const localEnd = Math.max(0, pageEnd.value - groupStart)
  return items.slice(localStart, localEnd)
}

/** Filename matches visible on the current separated-mode page. */
const pagedFilenameResults = computed(() => {
  const results = workspaceStore.searchResults
  return results ? sliceSeparatedGroup(results.filename_results, 0) : []
})

/** Fulltext matches visible after filename matches on the current page. */
const pagedFulltextResults = computed(() => {
  const results = workspaceStore.searchResults
  if (!results) return []
  return sliceSeparatedGroup(results.fulltext_results, results.filename_results.length)
})

/** Semantic matches visible after the two lexical groups on the current page. */
const pagedSemanticResults = computed(() => {
  const results = workspaceStore.searchResults
  if (!results) return []
  const groupStart = results.filename_results.length + results.fulltext_results.length
  return sliceSeparatedGroup(results.semantic_results, groupStart)
})

/** Unified results visible on the current page. */
const pagedUnifiedResults = computed(() => unifiedResults.value.slice(pageStart.value, pageEnd.value))

/** Moves to a bounded page and clears a preview selected on the previous page. */
function setPage(page: number) {
  const nextPage = Math.min(totalPages.value, Math.max(1, page))
  if (nextPage === currentPage.value) return
  currentPage.value = nextPage
  workspaceStore.closeEditorSidebar()
}

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
  }
})

watch(() => workspaceStore.searchResults, () => {
  currentPage.value = 1
  workspaceStore.closeEditorSidebar()
})

onMounted(() => {
  syncFromStore()
})
</script>

<template>
  <div class="search-page" :class="{ searched: hasSearched }">
    <!-- Animating search stage (absolute, transitions top) -->
    <div class="search-stage" :class="{ pinned: hasSearched }">
      <Transition name="title-fade">
        <div v-if="!hasSearched" class="hero-title">
          <SplitText class="hero-title-text" text="知识库搜索" tag="h1" :trigger-on-mount="true" />
          <p>在知识库中搜索文件、内容和语义匹配</p>
        </div>
      </Transition>

      <div class="search-box-wrap">
        <SearchPalette variant="page" @submit="onSubmit" />
      </div>
    </div>

    <!-- Results (below absolute search-stage, scrolls with page) -->
    <div v-if="hasSearched && workspaceStore.searchQuery" class="results-area">
      <div class="results-workspace">
        <div class="results-list-pane">
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
              <IcIcon v-if="unifiedMode" name="layers" :size="12" />
              <IcIcon v-else name="view-list" :size="12" />
              <span>{{ unifiedMode ? '联合搜索' : '搜索分离' }}</span>
            </button>
          </div>

          <div v-if="workspaceStore.searchResults" class="results-container">
        <!-- === SEPARATED MODE === -->
            <template v-if="!unifiedMode">
              <div v-if="pagedFilenameResults.length" class="result-group">
                <div class="group-label">文件</div>
                <button
                  v-for="item in pagedFilenameResults"
                  :key="item.path"
                  class="result-card"
                  :class="{ selected: workspaceStore.editorSidebarOpen && workspaceStore.selectedPath === resolveResultNode(item.path)?.path }"
                  type="button"
                  @click="previewResult(item.path)"
                  @dblclick="openResult(item.path)"
                >
                  <div class="card-title">
                    <span class="card-name" v-html="highlightMatch(item.name, workspaceStore.searchQuery)" />
                  </div>
                  <div class="card-path">{{ item.path }}</div>
                </button>
              </div>

              <div v-if="pagedFulltextResults.length" class="result-group">
                <div class="group-label">内容匹配</div>
                <button
                  v-for="item in pagedFulltextResults"
                  :key="item.source_uri"
                  class="result-card"
                  :class="{ selected: workspaceStore.editorSidebarOpen && workspaceStore.selectedPath === resolveResultNode(item.source_uri)?.path }"
                  type="button"
                  @click="previewResult(item.source_uri)"
                  @dblclick="openResult(item.source_uri)"
                >
                  <div class="card-title">
                    <span class="card-name">{{ baseName(item.source_uri) }}</span>
                  </div>
                  <div class="card-snippet" v-html="highlightMatch(item.snippet, workspaceStore.searchQuery)" />
                  <div class="card-path">{{ item.source_uri }}</div>
                </button>
              </div>

              <div v-if="pagedSemanticResults.length" class="result-group">
                <div class="group-label">语义匹配</div>
                <button
                  v-for="item in pagedSemanticResults"
                  :key="(item as Record<string, unknown>).memory_id as string"
                  class="result-card"
                  :class="{ selected: workspaceStore.editorSidebarOpen && workspaceStore.selectedPath === resolveResultNode((item as Record<string, unknown>).source_uri as string)?.path }"
                  type="button"
                  @click="previewResult((item as Record<string, unknown>).source_uri as string)"
                  @dblclick="openResult((item as Record<string, unknown>).source_uri as string)"
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
                v-for="item in pagedUnifiedResults"
                :key="item.path"
                class="result-card"
                :class="{ selected: workspaceStore.editorSidebarOpen && workspaceStore.selectedPath === resolveResultNode(item.path)?.path }"
                type="button"
                @click="previewResult(item.path)"
                @dblclick="openResult(item.path)"
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

          <nav
            v-if="workspaceStore.searchResults && totalPages > 1"
            class="pagination"
            aria-label="搜索结果分页"
          >
            <button
              class="pagination-button pagination-previous"
              type="button"
              :disabled="currentPage === 1"
              @click="setPage(currentPage - 1)"
            >
              上一页
            </button>
            <span class="pagination-status" aria-live="polite">
              {{ currentPage }} / {{ totalPages }}
            </span>
            <button
              class="pagination-button pagination-next"
              type="button"
              :disabled="currentPage === totalPages"
              @click="setPage(currentPage + 1)"
            >
              下一页
            </button>
          </nav>

        </div>

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

.hero-title h1,
.hero-title-text {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(32px * var(--font-scale));
  font-weight: 750;
  letter-spacing: 0;
}

.hero-title-text,
.hero-title :deep(.split-text),
.hero-title :deep(.split-char) {
  font-family: var(--font-ui) !important;
}

.hero-title p {
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: calc(13px * var(--font-scale));
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
  position: relative;
  overflow: hidden;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.search-box::before {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  margin: auto;
  content: "";
  border-radius: 50%;
  display: block;
  width: 30em;
  height: 30em;
  left: -5em;
  text-align: center;
  transition: box-shadow 0.5s ease-out;
  z-index: 0;
  pointer-events: none;
}

:root[data-theme="dark"] .search-box {
  background: #1c1c20;
  border-color: #2a2a30;
}

:root[data-theme="light"] .search-box {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.search-box:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.search-box-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
  position: relative;
  z-index: 1;
}

.search-box-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(15px * var(--font-scale));
  position: relative;
  z-index: 1;
}

.search-box-input::placeholder {
  color: var(--color-text-muted);
}

.search-box-spinner {
  flex-shrink: 0;
  color: var(--color-primary);
  animation: spin 700ms linear infinite;
  position: relative;
  z-index: 1;
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
  position: relative;
  z-index: 1;
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
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  font-size: calc(13px * var(--font-scale));
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  outline: none;
  overflow: hidden;
  text-align: center;
  position: relative;
  z-index: 1;
  transition: color 0.3s 0.1s ease-out;
}

.search-box-submit::before {
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

.search-box-submit:hover {
  color: #fff;
  border-color: var(--color-primary);
}

.search-box-submit:hover::before {
  box-shadow: inset 0 0 0 10em var(--color-primary);
}

/* Toggles */
.search-box-toggles {
  display: flex;
  align-items: center;
  gap: 8px;
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
  padding: 4px 16px;
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
  padding: 4px 16px;
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
}

.results-workspace {
  display: grid;
  width: min(90%, 720px);
  margin: 0 auto;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-16);
  transition: width 220ms ease;
}

.results-list-pane {
  min-width: 0;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 16px;
}

.results-count {
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
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
  font-size: calc(11px * var(--font-scale));
  cursor: pointer;
}

.mode-toggle.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.results-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-12);
  min-height: 44px;
  margin-top: var(--space-16);
}

.pagination-button {
  min-width: 64px;
  height: 32px;
  padding: 0 var(--space-10);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canvas-soft);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.pagination-button:hover:not(:disabled) {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.pagination-button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.pagination-button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.pagination-status {
  min-width: 56px;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  text-align: center;
}

.results-empty {
  width: 100%;
  text-align: center;
  padding: 60px 0;
  color: var(--color-text-muted);
  font-size: calc(14px * var(--font-scale));
}

/* Result groups (separated mode) */
.result-group {
  margin-bottom: 16px;
}

.group-label {
  padding: 6px 12px;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
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
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition:
    background 120ms ease,
    border-color 120ms ease;
}

.result-card:hover {
  background: var(--color-primary-soft);
}

.result-card.selected {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.result-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-name {
  font-size: calc(15px * var(--font-scale));
  font-weight: 650;
  color: var(--color-text);
}

.card-name :deep(mark) {
  background: rgba(255, 196, 0, 0.35);
  color: inherit;
  border-radius: 2px;
}

.card-snippet {
  font-size: calc(13px * var(--font-scale));
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
  font-size: calc(13px * var(--font-scale));
  color: var(--color-text-muted);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-path {
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
  font-family: var(--font-ui);
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
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
}

@media (prefers-reduced-motion: reduce) {
  .results-workspace {
    transition: none;
  }
}
</style>
