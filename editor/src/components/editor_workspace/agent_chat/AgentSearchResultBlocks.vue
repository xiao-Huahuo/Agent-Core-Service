<!--
  Agent-mounted four-library search results.

  Usage:
  MessageList supplies only results cited by the final Agent answer. Cards use
  the same native renderer as SearchPage and route clicks by Agent layout mode.
-->
<script setup lang="ts">
import { computed } from 'vue'

import SearchNativeResultCard from '@/components/search_page/SearchNativeResultCard.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { SEARCH_SOURCES } from '@/types/unifiedSearch'
import type { SearchSource, UnifiedSearchResult } from '@/types/unifiedSearch'
import { SEARCH_SOURCE_PRESENTATION } from '@/utils/searchSourcePresentation'

defineOptions({ name: 'AgentSearchResultBlocks' })

const props = defineProps<{
  results: UnifiedSearchResult[]
  compact?: boolean
}>()

const workspaceStore = useWorkspaceStore()

/** Preserve split-search source order while omitting libraries without mounted results. */
const sourceGroups = computed(() => SEARCH_SOURCES.flatMap((source) => {
  const results = props.results.filter((result) => result.source === source)
  return results.length ? [{ source, results }] : []
}))

/** Reuse the four native split-search layouts inside each independent source row. */
function nativeGridClass(source: SearchSource): string {
  return {
    files: 'file-medium-grid',
    library: 'library-card-grid',
    components: 'component-card-grid',
    literature: 'literature-file-list',
  }[source]
}

/** Open a mounted result through the layout-aware shared workspace route. */
function openResult(result: UnifiedSearchResult): void {
  void workspaceStore.openAgentSearchResult(result, Boolean(props.compact))
}
</script>

<template>
  <div class="agent-search-result-blocks" :class="{ compact }" aria-label="Agent 挂载的搜索结果">
    <section
      v-for="group in sourceGroups"
      :key="group.source"
      class="agent-search-result-section"
      :data-source="group.source"
    >
      <header class="agent-search-result-heading">
        <h3>{{ SEARCH_SOURCE_PRESENTATION[group.source].label }}</h3>
        <span>{{ group.results.length }}</span>
      </header>
      <div :class="[nativeGridClass(group.source), { compact }]">
        <SearchNativeResultCard
          v-for="result in group.results"
          :key="result.id"
          :result="result"
          @activate="openResult"
          @open="openResult"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.agent-search-result-blocks {
  display: grid;
  gap: var(--space-16);
  width: min(100%, 760px);
  margin-bottom: var(--space-12);
  container-type: inline-size;
}

.agent-search-result-section {
  min-width: 0;
}

.agent-search-result-section + .agent-search-result-section {
  padding-top: var(--space-12);
  border-top: 1px solid var(--color-border);
}

.agent-search-result-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--space-10);
}

.agent-search-result-heading h3 {
  margin: 0;
  color: var(--color-text);
  font-size: calc(14px * var(--font-scale));
}

.agent-search-result-heading span {
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.file-medium-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(clamp(112px, 16cqi, 156px), 1fr));
  gap: clamp(10px, 1.2vw, 18px);
}

.library-card-grid,
.component-card-grid {
  column-width: 260px;
  column-gap: 18px;
}

.library-card-grid { column-width: 180px; }

.literature-file-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-10);
}

.file-medium-grid.compact,
.literature-file-list.compact {
  grid-template-columns: minmax(0, 1fr);
}

.library-card-grid.compact,
.component-card-grid.compact {
  columns: 1;
}

@container (max-width: 560px) {
  .file-medium-grid,
  .literature-file-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .library-card-grid,
  .component-card-grid {
    columns: 1;
  }
}
</style>
