<!--
  Four-library unified search page.

  Usage:
  EditorWorkspace renders this view for mainView === 'search'. The page shares
  one backend result set between a ranked unified list and four vertically
  stacked native library presentations.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import PixelLoader from '@/components/common/PixelLoader.vue'
import SearchPalette from '@/components/editor_workspace/SearchPalette.vue'
import SplitText from '@/components/editor_workspace/SplitText.vue'
import SearchNativeResultCard from '@/components/search_page/SearchNativeResultCard.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeFileNode } from '@/types/knowledge'
import type { SearchSource, UnifiedSearchResult } from '@/types/unifiedSearch'
import { highlightMatch } from '@/utils/highlight'
import { SEARCH_SOURCE_PRESENTATION } from '@/utils/searchSourcePresentation'

defineOptions({ name: 'SearchPage' })

const workspaceStore = useWorkspaceStore()
const hasSearched = ref(false)
const PAGE_SIZE = 20
const SPLIT_BATCH_SIZE = 8
const currentPage = ref(1)
const splitLimits = ref<Record<SearchSource, number>>({ files: 8, library: 8, components: 8, literature: 8 })

const modeLabels = { title: '标题', fulltext: '内容', semantic: '语义' } as const

const results = computed(() => workspaceStore.searchResults?.results ?? [])
const totalPages = computed(() => Math.max(1, Math.ceil(results.value.length / PAGE_SIZE)))
const pagedResults = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return results.value.slice(start, start + PAGE_SIZE)
})

/** Return one backend source group unchanged. */
function sourceResults(source: SearchSource): UnifiedSearchResult[] {
  return workspaceStore.searchResults?.groups[source] ?? []
}

/** Return the currently revealed native-card batch for one source section. */
function visibleSourceResults(source: SearchSource): UnifiedSearchResult[] {
  return sourceResults(source).slice(0, splitLimits.value[source])
}

/** Reveal the next native-card batch without issuing another search request. */
function showMore(source: SearchSource): void {
  splitLimits.value[source] += SPLIT_BATCH_SIZE
}

/** Submit the normalized query from the large page search control. */
function onSubmit(): void {
  const query = workspaceStore.searchQuery.trim()
  if (!query) return
  hasSearched.value = true
  currentPage.value = 1
  workspaceStore.closeEditorSidebar()
  void workspaceStore.performSearch(query)
}

/** Resolve a search file path back to the current live workspace node. */
function resolveFileNode(path: string): KnowledgeFileNode | undefined {
  const normalized = path.replace(/\\/g, '/')
  return workspaceStore.flatNodes?.find((node) => node.path === normalized)
    ?? workspaceStore.flatNodes?.find((node) => node.name === normalized.split('/').pop())
}

/** Preview a file through the same shared sidebar used by the resource manager. */
async function previewFile(node: KnowledgeFileNode): Promise<void> {
  if (node.isDir) return
  await workspaceStore.openEditorSidebar(resolveFileNode(node.path) ?? node)
}

/** Enter the regular editor workflow for one file result. */
function openFile(node: KnowledgeFileNode): void {
  const liveNode = resolveFileNode(node.path) ?? node
  workspaceStore.setMainView('editor')
  void workspaceStore.selectFile(liveNode)
}

/** Route a unified result row through its source's existing navigation. */
function openUnifiedResult(result: UnifiedSearchResult): void {
  if (result.source === 'files') {
    void previewFile(result.item as unknown as KnowledgeFileNode)
    return
  }
  void workspaceStore.openSearchResultSidebar(result)
}

/** Open a non-file split card in the same shared editor-sidebar column. */
function openResultSidebar(result: UnifiedSearchResult): void {
  void workspaceStore.openSearchResultSidebar(result)
}

/** Route a native card's stronger open gesture through its existing workflow. */
function openNativeResult(result: UnifiedSearchResult): void {
  if (result.source === 'files') {
    openFile(result.item as unknown as KnowledgeFileNode)
    return
  }
  openResultSidebar(result)
}

/** Preserve the four split-mode grid layouts around the shared native card. */
function nativeGridClass(source: SearchSource): string {
  return {
    files: 'file-medium-grid',
    library: 'library-card-grid',
    components: 'component-card-grid',
    literature: 'literature-file-list',
  }[source]
}

/** Move to a bounded unified-list page and clear a stale file preview. */
function setPage(page: number): void {
  currentPage.value = Math.min(totalPages.value, Math.max(1, page))
  workspaceStore.closeEditorSidebar()
}

/** Restore the searched layout when returning to retained results. */
function syncFromStore(): void {
  hasSearched.value = Boolean(workspaceStore.searchQuery.trim() && workspaceStore.searchResults)
}

watch(() => workspaceStore.searchResults, () => {
  currentPage.value = 1
  splitLimits.value = { files: 8, library: 8, components: 8, literature: 8 }
  if (workspaceStore.searchResults) hasSearched.value = true
  workspaceStore.closeEditorSidebar()
})
watch(() => workspaceStore.mainView, (view) => { if (view === 'search') syncFromStore() })
onMounted(syncFromStore)
</script>

<template>
  <div class="search-page" :class="{ searched: hasSearched }">
    <div class="search-stage" :class="{ pinned: hasSearched }">
      <Transition name="title-fade">
        <div v-if="!hasSearched" class="hero-title">
          <SplitText class="hero-title-text" text="全库搜索" tag="h1" :trigger-on-mount="true" />
        </div>
      </Transition>
      <SearchPalette variant="page" @submit="onSubmit" />
    </div>

    <div v-if="hasSearched && workspaceStore.searchQuery" class="results-area">
      <header class="results-header">
        <span class="results-count">{{ workspaceStore.searchResults?.total ?? 0 }} 个结果</span>
        <div class="presentation-switch" aria-label="搜索结果样式">
          <span class="presentation-indicator" :class="{ split: !workspaceStore.searchUnified }" aria-hidden="true"></span>
          <button type="button" :class="{ active: workspaceStore.searchUnified }" @click="workspaceStore.searchUnified = true">
            <IcIcon name="view-list" :size="14" />统一样式
          </button>
          <button type="button" :class="{ active: !workspaceStore.searchUnified }" @click="workspaceStore.searchUnified = false">
            <IcIcon name="layers" :size="14" />分裂样式
          </button>
        </div>
      </header>

      <div v-if="workspaceStore.searching" class="search-status" role="status">
        <PixelLoader />正在搜索已选中的库
      </div>
      <div v-else-if="workspaceStore.searchError" class="search-status error" role="alert">{{ workspaceStore.searchError }}</div>

      <template v-else-if="workspaceStore.searchResults">
        <section v-if="workspaceStore.searchUnified" class="unified-results" aria-label="统一搜索结果">
          <button
            v-for="result in pagedResults"
            :key="`${result.source}:${result.id}`"
            class="unified-result-row"
            type="button"
            @click="openUnifiedResult(result)"
          >
            <span class="result-source" :style="{ color: SEARCH_SOURCE_PRESENTATION[result.source].color }">
              <IcIcon class="source-result-icon" :name="SEARCH_SOURCE_PRESENTATION[result.source].icon" :size="13" />
              {{ SEARCH_SOURCE_PRESENTATION[result.source].label }}
            </span>
            <strong v-html="highlightMatch(result.title, workspaceStore.searchQuery)"></strong>
            <span v-if="result.snippet" class="result-snippet" v-html="highlightMatch(result.snippet, workspaceStore.searchQuery)"></span>
            <span class="result-bottom">
              <span class="result-locator">{{ result.locator }}</span>
              <span class="matched-modes">{{ result.matched_modes.map((mode) => modeLabels[mode]).join(' · ') }}</span>
            </span>
          </button>
          <nav v-if="totalPages > 1" class="pagination" aria-label="统一搜索结果分页">
            <button type="button" :disabled="currentPage === 1" @click="setPage(currentPage - 1)">上一页</button>
            <span>{{ currentPage }} / {{ totalPages }}</span>
            <button type="button" :disabled="currentPage === totalPages" @click="setPage(currentPage + 1)">下一页</button>
          </nav>
        </section>

        <div v-else class="split-results" aria-label="分裂搜索结果">
          <section
            v-for="source in workspaceStore.searchSources"
            :key="source"
            class="split-section"
            :class="`split-${source}`"
          >
            <header class="split-section-header">
              <h2>{{ SEARCH_SOURCE_PRESENTATION[source].label }}</h2>
              <span>{{ workspaceStore.searchResults.counts[source] }}</span>
            </header>
            <div v-if="sourceResults(source).length === 0" class="source-empty">此库没有匹配结果</div>

            <div v-else :class="nativeGridClass(source)">
              <SearchNativeResultCard
                v-for="result in visibleSourceResults(source)"
                :key="result.id"
                :result="result"
                :selected="result.source === 'files' && workspaceStore.editorSidebarOpen && workspaceStore.selectedPath === result.locator"
                @activate="openUnifiedResult"
                @open="openNativeResult"
              />
            </div>

            <button v-if="splitLimits[source] < sourceResults(source).length" class="show-more" type="button" @click="showMore(source)">
              显示更多
            </button>
          </section>
        </div>
        <div v-if="workspaceStore.searchResults.total === 0" class="results-empty">无匹配结果</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.search-page { position: relative; height: 100%; overflow-y: auto; scrollbar-gutter: stable; background: var(--color-canvas); container-type: inline-size; }
.search-stage { position: absolute; top: 35%; left: 50%; z-index: 5; display: grid; width: min(88%, 680px); gap: 28px; transform: translateX(-50%); transition: top 350ms cubic-bezier(.4, 0, .2, 1); }
.search-stage.pinned { top: 16px; }
.hero-title { text-align: center; pointer-events: none; }
.hero-title h1, .hero-title-text { margin: 0; color: var(--color-text); font-family: var(--font-ui); font-size: calc(32px * var(--font-scale)); font-weight: 750; }
.hero-title-text, .hero-title :deep(.split-text), .hero-title :deep(.split-char) { font-family: var(--font-ui) !important; }
.title-fade-leave-active { transition: opacity 250ms ease, transform 250ms ease; }
.title-fade-leave-to { opacity: 0; transform: translateY(-14px); }
.results-area { width: min(1180px, calc(100% - 48px)); margin: 0 auto; padding: 132px 0 80px; }
.results-header { display: flex; min-height: 42px; align-items: center; justify-content: space-between; gap: var(--space-16); border-bottom: 1px solid var(--color-border); }
.results-count { color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
.presentation-switch { position: relative; display: grid; grid-template-columns: repeat(2, 104px); align-items: stretch; }
.presentation-indicator { position: absolute; left: 0; bottom: 0; width: 50%; height: 2px; background: var(--color-primary); transform: translateX(0); transition: transform 240ms cubic-bezier(.23, 1, .32, 1); }
.presentation-indicator.split { transform: translateX(100%); }
.presentation-switch button { position: relative; z-index: 1; display: inline-flex; align-items: center; justify-content: center; gap: var(--space-6); min-height: 36px; padding: 0 var(--space-8); border: 0; background: transparent; color: var(--color-text-muted); cursor: pointer; transition: color var(--transition-fast); }
.presentation-switch button.active { color: var(--color-primary); }
.search-status, .results-empty, .source-empty { display: flex; min-height: 120px; align-items: center; justify-content: center; gap: var(--space-8); color: var(--color-text-muted); font-size: calc(13px * var(--font-scale)); }
.search-status.error { color: var(--color-danger); }
.unified-results { width: min(820px, 100%); margin: var(--space-16) auto 0; }
.unified-result-row { position: relative; display: grid; width: 100%; min-width: 0; gap: var(--space-6); padding: 14px 116px 14px 14px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: var(--color-text); text-align: left; cursor: pointer; transition: background 120ms ease, border-color 120ms ease; }
.unified-result-row:hover { background: var(--color-primary-soft); }
.unified-result-row:focus-visible { border-color: var(--color-primary); outline: 0; }
.unified-result-row strong { overflow: hidden; font-size: calc(15px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.result-source { position: absolute; top: 15px; right: 14px; display: inline-flex; align-items: center; gap: var(--space-4); font-size: calc(11px * var(--font-scale)); font-weight: 600; }
.result-snippet { overflow: hidden; color: var(--color-text-secondary); font-size: calc(13px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.result-bottom { display: flex; min-width: 0; justify-content: space-between; gap: var(--space-12); color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }
.result-locator { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.matched-modes { flex: 0 0 auto; }
.unified-result-row :deep(mark) { background: color-mix(in srgb, var(--color-warning) 38%, transparent); color: inherit; }
.pagination { display: flex; min-height: 48px; align-items: center; justify-content: center; gap: var(--space-12); margin-top: var(--space-12); }
.pagination button, .show-more { min-height: 32px; border: 0; background: transparent; color: var(--color-primary); cursor: pointer; }
.pagination button:disabled { color: var(--color-text-muted); cursor: not-allowed; opacity: .45; }
.pagination span { color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
.split-results { display: grid; gap: 40px; padding-top: 24px; }
.split-section { min-width: 0; padding-bottom: 32px; border-bottom: 1px solid var(--color-border); }
.split-section:last-child { border-bottom: 0; }
.split-section-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: var(--space-16); }
.split-section-header h2 { margin: 0; color: var(--color-text); font-size: calc(18px * var(--font-scale)); }
.split-section-header span { color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
.file-medium-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(clamp(112px, 16cqi, 156px), 1fr)); gap: clamp(10px, 1.2vw, 18px); }
.library-card-grid, .component-card-grid { column-width: 260px; column-gap: 18px; }
.library-card-grid { column-width: 180px; }
.literature-file-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-10); }
.show-more { display: block; margin: var(--space-12) auto 0; }
@container (max-width: 820px) {
  .results-area { width: calc(100% - 32px); }
  .literature-file-list { grid-template-columns: minmax(0, 1fr); }
  .library-card-grid, .component-card-grid { column-width: 220px; }
}
@container (max-width: 560px) {
  .search-stage { width: calc(100% - 24px); }
  .results-area { width: calc(100% - 24px); padding-top: 126px; }
  .results-header { align-items: flex-end; }
  .presentation-switch button { font-size: 0; }
  .presentation-switch { grid-template-columns: repeat(2, 36px); }
  .presentation-switch button { padding: 0; }
  .presentation-switch button :deep(svg) { width: 17px; height: 17px; }
  .unified-result-row { padding: 34px 12px 12px; }
  .result-source { top: 10px; left: auto; right: 12px; }
  .result-bottom { display: grid; }
  .matched-modes { justify-self: start; }
  .file-medium-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .library-card-grid, .component-card-grid { columns: 1; }
}
@media (prefers-reduced-motion: reduce) { .search-stage, .title-fade-leave-active, .presentation-indicator { transition: none; } }
</style>
