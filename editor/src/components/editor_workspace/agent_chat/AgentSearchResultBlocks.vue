<!--
  Agent-mounted four-library search results.

  Usage:
  MessageList supplies only results cited by the final Agent answer. Cards use
  the same native renderer as SearchPage and route clicks by Agent layout mode.
-->
<script setup lang="ts">
import SearchNativeResultCard from '@/components/search_page/SearchNativeResultCard.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { UnifiedSearchResult } from '@/types/unifiedSearch'

defineOptions({ name: 'AgentSearchResultBlocks' })

const props = defineProps<{
  results: UnifiedSearchResult[]
  compact?: boolean
}>()

const workspaceStore = useWorkspaceStore()

/** Open a mounted result through the layout-aware shared workspace route. */
function openResult(result: UnifiedSearchResult): void {
  void workspaceStore.openAgentSearchResult(result, Boolean(props.compact))
}
</script>

<template>
  <div class="agent-search-result-blocks" :class="{ compact }" aria-label="Agent 挂载的搜索结果">
    <div
      v-for="result in results"
      :key="`${result.source}:${result.id}`"
      class="agent-search-result-block"
      :class="`source-${result.source}`"
    >
      <SearchNativeResultCard :result="result" @activate="openResult" @open="openResult" />
    </div>
  </div>
</template>

<style scoped>
.agent-search-result-blocks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
  gap: var(--space-10);
  width: min(100%, 760px);
  margin-bottom: var(--space-12);
  container-type: inline-size;
}

.agent-search-result-blocks.compact {
  grid-template-columns: minmax(0, 1fr);
}

.agent-search-result-block,
.agent-search-result-block :deep(> *) {
  min-width: 0;
  width: 100%;
}

.agent-search-result-block.source-files {
  max-width: 180px;
}
</style>
