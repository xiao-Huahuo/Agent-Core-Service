<!--
  Knowledge source references display for Agent chat bubbles.

  Usage:
  Shows retrieved knowledge source files below assistant messages as individual
  file entries. Each source can be clicked to navigate to that file.
-->
<script setup lang="ts">
import { ChevronDown, ExternalLink } from 'lucide-vue-next'
import { ref } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { SourceItem } from '@/stores/chat'

const props = defineProps<{
  sources: SourceItem[]
}>()

const workspaceStore = useWorkspaceStore()
const expanded = ref(false)

function baseName(uri: string): string {
  const parts = uri.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? uri
}

function toggle() {
  expanded.value = !expanded.value
}

function openSource(uri: string) {
  const flatNodes = workspaceStore.flatNodes ?? []
  let node = flatNodes.find((n) => n.path === uri)
  if (!node) {
    const name = baseName(uri)
    node = flatNodes.find((n) => n.path.endsWith(`/${name}`) || n.name === name)
  }
  if (node) {
    workspaceStore.setMainView('editor')
    workspaceStore.selectFile(node)
  }
}
</script>

<template>
  <div v-if="sources.length > 0" class="knowledge-sources">
    <button class="sources-toggle" type="button" @click="toggle">
      <ChevronDown :size="12" class="toggle-chevron" :class="{ rotated: expanded }" />
      <span class="sources-label">来源</span>
      <span class="sources-count">{{ sources.length }}</span>
    </button>
    <div v-if="expanded" class="sources-list">
      <button
        v-for="(source, index) in sources"
        :key="source.source_uri + index"
        class="source-item"
        type="button"
        @click="openSource(source.source_uri)"
      >
        <span class="source-index">{{ source.citation_id ?? index + 1 }}</span>
        <span class="source-name">{{ baseName(source.source_uri) }}</span>
        <ExternalLink :size="10" class="source-link-icon" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.knowledge-sources {
  width: 100%;
  margin-top: var(--space-8);
}

.sources-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-4) 0;
  border: 0;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  transition:
    color var(--transition-fast),
    opacity var(--transition-fast);
}

.sources-toggle:hover {
  color: var(--color-text-secondary);
  opacity: 1;
}

.toggle-chevron {
  transition: transform 180ms ease;
}

.toggle-chevron.rotated {
  transform: rotate(0deg);
}

.toggle-chevron:not(.rotated) {
  transform: rotate(-90deg);
}

.sources-label {
  opacity: 0.55;
}

.sources-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 14px;
  height: 14px;
  padding: 0 4px;
  border-radius: 3px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 9px;
  font-weight: 650;
  line-height: 1;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-top: var(--space-6);
}

.source-item {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-4) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 11px;
  cursor: pointer;
  text-align: left;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.source-item:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.source-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  border-radius: 3px;
  background: var(--color-primary);
  color: #fff;
  font-size: 9px;
  font-weight: 650;
  flex-shrink: 0;
}

.source-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link-icon {
  flex-shrink: 0;
  opacity: 0.3;
  transition: opacity var(--transition-fast);
}

.source-item:hover .source-link-icon {
  opacity: 0.8;
}
</style>
