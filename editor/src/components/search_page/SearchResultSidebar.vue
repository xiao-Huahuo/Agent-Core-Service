<!--
  Editable non-file search result sidebar.

  Usage:
  EditorWorkspace mounts this component inside its existing draggable editor
  sidebar column for library, component, and literature search results.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { listLibraryTags, updateLibraryItem } from '@/api/library'
import { writeKnowledgeFile } from '@/api/knowledge'
import { updateComponentLibraryItem } from '@/api/componentLibrary'
import { getSmartFormDb } from '@/api/smartForms'
import { patchLiteratureRow, type LiteratureEntry } from '@/api/literatureReading'
import ComponentLibraryDetail from '@/components/component_library/ComponentLibraryDetail.vue'
import PixelLoader from '@/components/common/PixelLoader.vue'
import IcIcon from '@/components/common/IcIcon.vue'
import EditorSidebarCloseButton from '@/components/editor_workspace/EditorSidebarCloseButton.vue'
import EditorPane from '@/components/editor_workspace/EditorPane.vue'
import LibraryItemDialog from '@/components/library_view/LibraryItemDialog.vue'
import LiteratureEntryCard from '@/components/literature_reading/LiteratureEntryCard.vue'
import type { SmartLiteratureForm, SmartRow } from '@/components/smart_forms/smartLiteratureTable'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ComponentLibraryItem } from '@/types/componentLibrary'
import type { LibraryItem, LibraryTag } from '@/types/knowledge'
import type { UnifiedSearchResult } from '@/types/unifiedSearch'
import { SEARCH_SOURCE_PRESENTATION } from '@/utils/searchSourcePresentation'

defineOptions({ name: 'SearchResultSidebar' })

const props = defineProps<{ result: UnifiedSearchResult }>()
const emit = defineEmits<{ close: [] }>()
const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

const loading = ref(false)
const saving = ref(false)
const libraryItem = ref<LibraryItem | null>(null)
const libraryTags = ref<LibraryTag[]>([])
const componentItem = ref<ComponentLibraryItem | null>(null)
const literatureEntry = ref<LiteratureEntry | null>(null)
const literatureForm = ref<SmartLiteratureForm | null>(null)
const literatureMode = ref<'fields' | 'content'>('fields')

const presentation = computed(() => SEARCH_SOURCE_PRESENTATION[props.result.source])
const literatureRow = computed<SmartRow | null>(() => (
  literatureForm.value?.rows.find((row) => row.id === literatureEntry.value?.row_id) ?? null
))

/** Load only the editor data missing from the search result DTO. */
async function loadEditor(): Promise<void> {
  loading.value = true
  literatureMode.value = 'fields'
  try {
    libraryItem.value = props.result.source === 'library' ? props.result.item as unknown as LibraryItem : null
    componentItem.value = props.result.source === 'components' ? props.result.item as unknown as ComponentLibraryItem : null
    literatureEntry.value = props.result.source === 'literature' ? props.result.item as unknown as LiteratureEntry : null
    if (props.result.source === 'library') {
      libraryTags.value = (await listLibraryTags(settingsStore.profile.userId)).tags
    } else if (literatureEntry.value) {
      literatureForm.value = (await getSmartFormDb(settingsStore.profile.userId, literatureEntry.value.form_id)).form
    }
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '侧栏内容加载失败')
  } finally {
    loading.value = false
  }
}

/** Persist library metadata and optional real-file text, then patch the visible result in place. */
async function saveLibrary(payload: {
  title: string
  description: string
  cover_mode: LibraryItem['cover_mode']
  cover_asset_id: string
  tags: string[]
  source_content?: string
}): Promise<void> {
  const item = libraryItem.value
  if (!item || saving.value) return
  saving.value = true
  try {
    if (payload.source_content !== undefined && item.source_path) {
      await writeKnowledgeFile(settingsStore.profile.userId, item.source_path, payload.source_content)
    }
    const response = await updateLibraryItem(item.item_id, {
      user_id: settingsStore.profile.userId,
      title: payload.title,
      description: payload.description,
      cover_mode: payload.cover_mode,
      cover_asset_id: payload.cover_asset_id,
      tags: payload.tags,
    })
    libraryItem.value = response.item
    workspaceStore.updateSearchSidebarResult({
      ...props.result,
      title: response.item.display_title,
      item: response.item as unknown as Record<string, unknown>,
    })
    workspaceStore.showToast('图书已保存')
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '图书保存失败')
  } finally {
    saving.value = false
  }
}

/** Persist edited Vue/HTML source and update only the current search item. */
async function saveComponentSource(source: string): Promise<void> {
  const item = componentItem.value
  if (!item || saving.value || source === item.source) return
  saving.value = true
  try {
    const response = await updateComponentLibraryItem(settingsStore.profile.userId, item.component_id, { source })
    componentItem.value = response.component
    workspaceStore.updateSearchSidebarResult({
      ...props.result,
      title: response.component.title,
      snippet: source.slice(0, 180),
      item: response.component as unknown as Record<string, unknown>,
    })
    workspaceStore.showToast('组件源码已保存')
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '组件源码保存失败')
  } finally {
    saving.value = false
  }
}

/** Persist one literature field and patch the result summary without querying search again. */
async function saveLiteratureCell(columnId: string, value: string): Promise<void> {
  const entry = literatureEntry.value
  if (!entry || saving.value) return
  saving.value = true
  try {
    const response = await patchLiteratureRow(
      settingsStore.profile.userId,
      entry.form_id,
      entry.row_id,
      { [columnId]: { value, status: 'ready' } },
    )
    literatureForm.value = response.form
    const nextEntry = {
      ...entry,
      title: columnId === 'title' ? value.trim() || entry.file_name : entry.title,
      content_excerpt: columnId === 'literature_content' ? ' '.concat(value).trim().slice(0, 240) : entry.content_excerpt,
    }
    literatureEntry.value = nextEntry
    workspaceStore.updateSearchSidebarResult({
      ...props.result,
      title: nextEntry.title,
      snippet: nextEntry.content_excerpt,
      item: nextEntry as unknown as Record<string, unknown>,
    })
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '文献字段保存失败')
  } finally {
    saving.value = false
  }
}

watch(() => props.result, () => { void loadEditor() }, { immediate: true })
</script>

<template>
  <section class="search-result-sidebar" :data-source="result.source">
    <header class="sidebar-editor-header">
      <span class="sidebar-title" :style="{ color: presentation.color }">
        <IcIcon :name="presentation.icon" :size="15" />
        {{ result.title }}
      </span>
      <span class="sidebar-header-actions">
        <span v-if="result.source === 'literature'" class="literature-mode-toggle" role="group" aria-label="文献侧栏视图">
          <span class="literature-mode-indicator" :class="{ content: literatureMode === 'content' }" aria-hidden="true"></span>
          <button type="button" :class="{ active: literatureMode === 'fields' }" aria-label="查看字段明细" @click="literatureMode = 'fields'">字段明细</button>
          <button type="button" :class="{ active: literatureMode === 'content' }" aria-label="查看文献内容" @click="literatureMode = 'content'">内容</button>
        </span>
        <EditorSidebarCloseButton @close="emit('close')" />
      </span>
    </header>

    <div v-if="loading" class="sidebar-loading" role="status" aria-label="正在加载侧栏编辑器"><PixelLoader /></div>

    <LibraryItemDialog
      v-else-if="result.source === 'library' && libraryItem"
      :open="true"
      :user-id="settingsStore.profile.userId"
      :item="libraryItem"
      :available-tags="libraryTags"
      embedded
      hide-header
      @close="emit('close')"
      @save="saveLibrary"
    />

    <ComponentLibraryDetail
      v-else-if="result.source === 'components' && componentItem"
      class="sidebar-component-editor"
      :item="componentItem"
      editable
      compact
      @save="saveComponentSource"
    />

    <EditorPane
      v-else-if="result.source === 'literature' && literatureMode === 'content'"
      class="sidebar-literature-content"
    />

    <div v-else-if="result.source === 'literature' && literatureEntry" class="sidebar-literature-editor">
      <LiteratureEntryCard
        :entry="literatureEntry"
        :form="literatureForm"
        :row="literatureRow"
        :selected="true"
        :renaming="false"
        :pending-column-ids="[]"
        default-expanded
        @update-cell="saveLiteratureCell"
      />
    </div>
  </section>
</template>

<style scoped>
.search-result-sidebar {
  display: grid;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 0;
  grid-template-rows: 42px minmax(0, 1fr);
  overflow: hidden;
  contain: inline-size;
  background: var(--color-canvas-soft);
  color: var(--color-text);
  font-family: var(--font-ui);
}

.sidebar-editor-header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  padding: var(--space-8) var(--space-10) 0;
}

.sidebar-title {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-6);
  overflow: hidden;
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-header-actions { display: inline-flex; flex: 0 0 auto; align-items: center; gap: var(--space-6); }
.literature-mode-toggle { position: relative; display: grid; grid-template-columns: 72px 44px; min-height: 28px; }
.literature-mode-indicator { position: absolute; left: 0; bottom: 0; width: 72px; height: 2px; background: var(--color-primary); transform: translateX(0); transition: transform 220ms cubic-bezier(.23,1,.32,1), width 220ms cubic-bezier(.23,1,.32,1); }
.literature-mode-indicator.content { width: 44px; transform: translateX(72px); }
.literature-mode-toggle button { position: relative; z-index: 1; border: 0; background: transparent; color: var(--color-text-muted); font-family: var(--font-ui); font-size: calc(11px * var(--font-scale)); cursor: pointer; }
.literature-mode-toggle button.active { color: var(--color-primary); }

.sidebar-loading { display: grid; place-items: center; min-height: 0; }
.sidebar-component-editor,
.sidebar-literature-editor,
.sidebar-literature-content { min-width: 0; min-height: 0; overflow: hidden; }
.sidebar-literature-editor { overflow-y: auto; padding: var(--space-8); }
.sidebar-literature-editor :deep(.literature-card) { min-height: 100%; border: 0; border-radius: 0; }

@media (max-width: 420px) {
  .literature-mode-toggle { grid-template-columns: 36px 36px; }
  .literature-mode-toggle button { width: 36px; padding: 0; overflow: hidden; font-size: 0; }
  .literature-mode-toggle button::after { font-size: 11px; }
  .literature-mode-toggle button:first-of-type::after { content: '字段'; }
  .literature-mode-toggle button:last-of-type::after { content: '内容'; }
  .literature-mode-indicator { width: 36px; }
  .literature-mode-indicator.content { width: 36px; transform: translateX(36px); }
}
</style>
