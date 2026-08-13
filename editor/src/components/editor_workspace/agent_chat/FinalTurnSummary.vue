<!--
  Final turn summary.

  Usage:
  Renders the persistent end-of-turn container below one completed assistant
  answer. Code-change statistics will be supplied by the change snapshot API;
  citations live here instead of being repeated beneath the response bubble.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import KnowledgeSources from '@/components/editor_workspace/agent_chat/KnowledgeSources.vue'
import type { AgentChangeSnapshot } from '@/api/agentChanges'
import type { SourceItem } from '@/stores/chat'

defineOptions({ name: 'FinalTurnSummary' })

const emit = defineEmits<{ undo: [] }>()

const props = defineProps<{
  sources: SourceItem[]
  changeSnapshot?: AgentChangeSnapshot | null
  undoing?: boolean
}>()

const expandedFiles = ref(false)
const activePanel = ref<'changes' | 'sources'>(props.changeSnapshot ? 'changes' : 'sources')
const panelSwitchRef = ref<HTMLElement | null>(null)
const panelSliderStyle = ref({ width: '0px', left: '0px' })
const visibleFiles = computed(() => expandedFiles.value ? props.changeSnapshot?.files ?? [] : (props.changeSnapshot?.files ?? []).slice(0, 3))
const hiddenFileCount = computed(() => Math.max(0, (props.changeSnapshot?.files.length ?? 0) - visibleFiles.value.length))
const panelTabs = computed(() => [
  ...(props.changeSnapshot ? [{ value: 'changes' as const, label: '变更', icon: 'edit-note' }] : []),
  ...(props.sources.length ? [{ value: 'sources' as const, label: '来源', icon: 'document' }] : []),
])

function updatePanelSlider() {
  void nextTick(() => {
    const container = panelSwitchRef.value
    if (!container) return
    const active = container.querySelector('.panel-switch-button.active') as HTMLElement | null
    if (!active) return
    panelSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

function setActivePanel(panel: 'changes' | 'sources') {
  activePanel.value = panel
  updatePanelSlider()
}

watch(panelTabs, (tabs) => {
  if (!tabs.some((tab) => tab.value === activePanel.value)) {
    activePanel.value = tabs[0]?.value ?? 'changes'
  }
  updatePanelSlider()
}, { immediate: true })

watch(activePanel, updatePanelSlider)
onMounted(updatePanelSlider)
</script>

<template>
  <section
    v-if="sources.length || changeSnapshot"
    class="final-turn-summary"
    :class="{ 'has-panel-switch': panelTabs.length > 1 }"
    aria-label="本轮结果"
  >
    <div v-if="panelTabs.length > 1" ref="panelSwitchRef" class="panel-switch" aria-label="本轮结果内容">
      <div class="panel-slider" :style="panelSliderStyle"></div>
      <button
        v-for="tab in panelTabs"
        :key="tab.value"
        class="panel-switch-button"
        :class="{ active: activePanel === tab.value }"
        type="button"
        @click="setActivePanel(tab.value)"
      >
        <IcIcon :name="tab.icon" :size="15" />
        <span>{{ tab.label }}</span>
      </button>
    </div>
    <div class="summary-content">
      <div v-if="changeSnapshot && activePanel === 'changes'" class="change-summary">
        <div class="change-heading" :class="{ 'has-panel-switch': panelTabs.length > 1 }">
          <span class="change-label">已编辑 {{ changeSnapshot.files.length }} 个文件</span>
          <button
            v-if="!changeSnapshot.is_undone && !changeSnapshot.is_imported"
            class="undo-button"
            type="button"
            :disabled="undoing"
            @click="emit('undo')"
          >
            <IcIcon name="replay" :size="14" />
            {{ undoing ? '撤销中' : '撤销' }}
          </button>
          <span v-else class="undo-done">已撤销</span>
        </div>
        <div class="change-stats">
          <span class="change-add">+{{ changeSnapshot.additions }}</span>
          <span class="change-remove">-{{ changeSnapshot.deletions }}</span>
        </div>
        <div class="change-files">
          <div v-for="file in visibleFiles" :key="file.path" class="change-file-row">
            <code>{{ file.path }}</code>
            <span><b class="change-add">+{{ file.additions }}</b><b class="change-remove">-{{ file.deletions }}</b></span>
          </div>
        </div>
        <button v-if="hiddenFileCount || expandedFiles" class="more-files-button" type="button" @click="expandedFiles = !expandedFiles">
          {{ expandedFiles ? '收起文件' : `再显示 ${hiddenFileCount} 个文件` }}
          <IcIcon name="chevron-down" :size="14" :class="{ rotated: expandedFiles }" />
        </button>
      </div>
      <div v-if="sources.length && activePanel === 'sources'" class="source-summary">
        <KnowledgeSources :sources="sources" default-expanded />
      </div>
    </div>
  </section>
</template>

<style scoped>
.final-turn-summary {
  position: relative;
  flex: 0 0 auto;
  width: min(100%, 760px);
  margin: 2px 0 var(--space-12);
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-surface-raised);
}

.panel-switch {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.panel-slider {
  position: absolute;
  top: 2px;
  z-index: 0;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-softer);
  transition: left 250ms ease, width 250ms ease;
  pointer-events: none;
}

.panel-switch-button {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 26px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
}

.panel-switch-button:hover,
.panel-switch-button.active {
  color: var(--color-primary);
}

.summary-content { display: grid; min-height: 0; padding: 18px 16px 16px; }

.change-summary {
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.change-heading {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  min-height: 34px;
  font-weight: 650;
}

.change-heading.has-panel-switch { padding-right: 128px; }
.change-label {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: calc(15px * var(--font-scale));
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.change-stats { display: flex; gap: var(--space-8); margin-top: 0; font-family: var(--font-code); font-size: calc(12px * var(--font-scale)); font-weight: 650; }
.change-add { color: var(--color-success); }
.change-remove { color: var(--color-danger); }

.undo-button {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 4px;
  height: 26px;
  margin-top: 0;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-tertiary);
  font: inherit;
  cursor: pointer;
}

.undo-button:hover:not(:disabled) {
  background: var(--color-primary-soft);
  color: var(--color-text-primary);
}

.undo-button:disabled { cursor: default; opacity: 0.6; }
.undo-done { display: inline-flex; align-items: center; flex: 0 0 auto; height: 26px; color: var(--color-text-tertiary); }

.change-files { margin: 10px -14px 0 -16px; border-top: 1px solid var(--color-border); }
.change-file-row { display: flex; align-items: center; gap: var(--space-8); min-height: 28px; padding: 0 16px; color: var(--color-text-secondary); font: inherit; }
.change-file-row + .change-file-row { border-top: 1px solid color-mix(in srgb, var(--color-border) 65%, transparent); }
.change-file-row code { min-width: 0; flex: 1; overflow: hidden; font: inherit; text-overflow: ellipsis; white-space: nowrap; }
.change-file-row span { display: flex; gap: var(--space-6); font: inherit; }
.change-file-row b { font-weight: 650; }
.more-files-button { display: inline-flex; align-items: center; gap: var(--space-4); width: calc(100% + 30px); margin: 0 -14px 0 -16px; padding: 7px 16px 0; border: 0; border-top: 1px solid var(--color-border); background: transparent; color: var(--color-text-secondary); font: inherit; font-size: calc(11px * var(--font-scale)); cursor: pointer; text-align: left; }
.more-files-button .ic-icon { transition: transform var(--transition-fast); }
.more-files-button .rotated { transform: rotate(180deg); }

.source-summary { min-width: 0; padding-left: 2px; }
.source-summary :deep(.knowledge-sources) { margin-top: 0; }
.source-summary :deep(.sources-toggle) { padding-top: 2px; }
</style>
