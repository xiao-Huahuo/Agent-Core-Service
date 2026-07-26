<!--
  Virtual library page.

  Usage:
  Provides an explorer-like virtual library surface for user-curated books and
  collections. It stores virtual metadata through /library APIs and opens real
  knowledge files through the existing workspace editor.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ArrowDownUp,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  CalendarClock,
  FilePlus2,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Link,
  RefreshCw,
  Search,
  Tags,
  Trash2,
  X,
} from 'lucide-vue-next'

import {
  createLibraryBook,
  createLibraryCollection,
  deleteLibraryItem,
  listLibraryItems,
  listLibraryTags,
  updateLibraryItem,
} from '@/api/library'
import { uploadKnowledgeFile } from '@/api/knowledge'
import LibraryCard from '@/components/library_view/LibraryCard.vue'
import LibraryCreateDialog from '@/components/library_view/LibraryCreateDialog.vue'
import LibraryItemDialog from '@/components/library_view/LibraryItemDialog.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { LibraryBreadcrumb, LibraryItem, LibraryTag } from '@/types/knowledge'

defineOptions({ name: 'LibraryView' })

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

const items = ref<LibraryItem[]>([])
const tags = ref<LibraryTag[]>([])
const breadcrumbs = ref<LibraryBreadcrumb[]>([])
const currentParentId = ref('')
const loading = ref(false)
const query = ref('')
const selectedTag = ref('')
const selectedContentType = ref('')
const sortKey = ref('updated_at')
const sortDirection = ref<'asc' | 'desc'>('desc')
const multiSelect = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const selectedItem = ref<LibraryItem | null>(null)
const drawerChildren = ref<LibraryItem[]>([])
const drawerChildrenLoading = ref(false)
const draggedItem = ref<LibraryItem | null>(null)
const editItem = ref<LibraryItem | null>(null)
const createDialogMode = ref<'book' | 'collection' | null>(null)
const backStack = ref<string[]>([])
const forwardStack = ref<string[]>([])

const selectedItems = computed(() => items.value.filter((item) => selectedIds.value.has(item.item_id)))
const hasSelection = computed(() => selectedIds.value.size > 0)
const canGoUp = computed(() => Boolean(currentParentId.value))
const canGoBack = computed(() => backStack.value.length > 0)
const canGoForward = computed(() => forwardStack.value.length > 0)
const virtualPath = computed(() => ['图书馆', ...breadcrumbs.value.map((crumb) => crumb.title)].join(' / '))
const drawerOpen = computed(() => Boolean(selectedItem.value) && !multiSelect.value)
const selectedDate = computed(() => formatDate(selectedItem.value?.source_mtime || selectedItem.value?.updated_at || ''))
const tagFilterTitle = computed(() => selectedTag.value ? `标签: ${selectedTag.value}` : '标签筛选: 全部')
const typeFilterTitle = computed(() => `类型筛选: ${contentTypeLabel(selectedContentType.value)}`)
const sortTitle = computed(() => `排序: ${sortLabel(sortKey.value)}`)

const contentTypeOptions = ['', 'knowledge_file', 'web_url', 'collection']
const sortOptions = ['updated_at', 'source_mtime', 'title', 'source_name']

watch(
  [query, selectedTag, selectedContentType, sortKey, sortDirection, currentParentId],
  () => {
    void loadItems()
  },
)

watch(multiSelect, (enabled) => {
  if (enabled) {
    selectedItem.value = null
  } else {
    selectedIds.value = new Set()
  }
})

watch(
  () => workspaceStore.pendingLibraryParentId,
  (parentId) => {
    if (!parentId) return
    navigateTo(parentId)
    workspaceStore.pendingLibraryParentId = ''
  },
  { immediate: true },
)

watch(selectedItem, (item) => {
  if (item?.item_type === 'collection') {
    void loadDrawerChildren(item.item_id)
  } else {
    drawerChildren.value = []
  }
})

onMounted(async () => {
  await Promise.all([loadItems(), loadTags(), workspaceStore.loadKnowledgeTree()])
})

async function loadItems() {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    const response = await listLibraryItems({
      userId: settingsStore.profile.userId,
      parentId: currentParentId.value,
      query: query.value,
      tag: selectedTag.value,
      contentType: selectedContentType.value,
      sort: sortKey.value,
      direction: sortDirection.value,
    })
    items.value = response.items
    breadcrumbs.value = response.breadcrumbs
    selectedIds.value = new Set([...selectedIds.value].filter((id) => response.items.some((item) => item.item_id === id)))
    if (selectedItem.value) {
      selectedItem.value = response.items.find((item) => item.item_id === selectedItem.value?.item_id) ?? null
    }
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  if (!settingsStore.profile.userId) return
  const response = await listLibraryTags(settingsStore.profile.userId)
  tags.value = response.tags
}

async function loadDrawerChildren(parentId: string) {
  if (!settingsStore.profile.userId) return
  drawerChildrenLoading.value = true
  try {
    const response = await listLibraryItems({
      userId: settingsStore.profile.userId,
      parentId,
      sort: 'updated_at',
      direction: 'desc',
    })
    drawerChildren.value = response.items
  } finally {
    drawerChildrenLoading.value = false
  }
}

function navigateTo(parentId: string, recordHistory = true) {
  const nextParentId = parentId.trim()
  if (nextParentId === currentParentId.value) return
  if (recordHistory) {
    backStack.value = [...backStack.value, currentParentId.value]
    forwardStack.value = []
  }
  currentParentId.value = nextParentId
  selectedIds.value = new Set()
  selectedItem.value = null
}

function goBack() {
  const target = backStack.value.at(-1)
  if (target === undefined) return
  backStack.value = backStack.value.slice(0, -1)
  forwardStack.value = [...forwardStack.value, currentParentId.value]
  navigateTo(target, false)
}

function goForward() {
  const target = forwardStack.value.at(-1)
  if (target === undefined) return
  forwardStack.value = forwardStack.value.slice(0, -1)
  backStack.value = [...backStack.value, currentParentId.value]
  navigateTo(target, false)
}

function goUp() {
  if (!currentParentId.value) return
  const parent = breadcrumbs.value.at(-2)?.item_id ?? ''
  navigateTo(parent)
}

function refreshLibrary() {
  void Promise.all([
    loadItems(),
    loadTags(),
    selectedItem.value?.item_type === 'collection' ? loadDrawerChildren(selectedItem.value.item_id) : Promise.resolve(),
    workspaceStore.loadKnowledgeTree(),
  ])
}

function goBreadcrumb(itemId: string) {
  navigateTo(itemId)
}

function selectItem(item: LibraryItem) {
  if (multiSelect.value) {
    toggleItem(item)
    return
  }
  selectedItem.value = selectedItem.value?.item_id === item.item_id ? null : item
}

function cycleTagFilter() {
  const tagNames = tags.value.map((tag) => tag.name)
  const options = ['', ...tagNames]
  const currentIndex = Math.max(0, options.indexOf(selectedTag.value))
  selectedTag.value = options[(currentIndex + 1) % options.length] ?? ''
}

function cycleContentTypeFilter() {
  const currentIndex = Math.max(0, contentTypeOptions.indexOf(selectedContentType.value))
  selectedContentType.value = contentTypeOptions[(currentIndex + 1) % contentTypeOptions.length] ?? ''
}

function cycleSortKey() {
  const currentIndex = Math.max(0, sortOptions.indexOf(sortKey.value))
  sortKey.value = sortOptions[(currentIndex + 1) % sortOptions.length] ?? 'updated_at'
}

async function openItem(item: LibraryItem) {
  if (item.item_type === 'collection') {
    navigateTo(item.item_id)
    return
  }
  if (item.content_type === 'web_url' && item.source_url) {
    window.open(item.source_url, '_blank')
    return
  }
  if (item.source_path) {
    workspaceStore.setMainView('editor')
    await workspaceStore.selectFile({
      name: item.source_name || item.source_path.split('/').pop() || item.source_path,
      path: item.source_path,
      isDir: false,
      mtime: item.source_mtime,
      indexStatus: item.index_status === 'missing' ? undefined : item.index_status || undefined,
      graphStatus: item.graph_status || undefined,
    })
  }
}

function toggleItem(item: LibraryItem) {
  const next = new Set(selectedIds.value)
  if (next.has(item.item_id)) {
    next.delete(item.item_id)
  } else {
    next.add(item.item_id)
  }
  selectedIds.value = next
}

function startDrag(item: LibraryItem) {
  draggedItem.value = item
}

async function dropOnItem(target: LibraryItem) {
  const source = draggedItem.value
  draggedItem.value = null
  if (!source || target.item_type !== 'collection' || source.item_id === target.item_id) return
  try {
    await updateLibraryItem(source.item_id, {
      user_id: settingsStore.profile.userId,
      parent_id: target.item_id,
    })
    selectedItem.value = null
    await loadItems()
    workspaceStore.showToast(`已移动到 ${target.display_title}`)
  } catch (error) {
    workspaceStore.showToast(`移动失败 — ${errorMessage(error)}`)
  }
}

function openCreateBookDialog() {
  createDialogMode.value = 'book'
}

function openCreateCollectionDialog() {
  createDialogMode.value = 'collection'
}

async function createFromDialog(payload: {
  title: string
  description: string
  tags: string[]
  cover_mode: LibraryItem['cover_mode']
  cover_asset_id: string
  file: File | null
}) {
  const mode = createDialogMode.value
  if (!mode) return
  try {
    if (mode === 'collection') {
      await createLibraryCollection({
        user_id: settingsStore.profile.userId,
        parent_id: currentParentId.value,
        title: payload.title,
        description: payload.description,
        cover_mode: payload.cover_mode,
        cover_asset_id: payload.cover_asset_id,
        tags: payload.tags,
      })
      workspaceStore.showToast('已新增集锦')
    } else {
      if (!payload.file) {
        workspaceStore.showToast('请选择真实文件')
        return
      }
      const result = await uploadKnowledgeFile(settingsStore.profile.userId, payload.file, '', false, 'rename') as { uploaded_path?: string; knowledge_dir?: string }
      const relativePath = relativeUploadedPath(result.uploaded_path ?? '', result.knowledge_dir ?? settingsStore.profile.knowledgeDir)
      if (!relativePath) {
        workspaceStore.showToast('上传完成但无法识别知识库相对路径')
        return
      }
      await createLibraryBook({
        user_id: settingsStore.profile.userId,
        parent_id: currentParentId.value,
        content_type: 'knowledge_file',
        source_path: relativePath,
        title: payload.title,
        description: payload.description,
        cover_mode: payload.cover_mode,
        cover_asset_id: payload.cover_asset_id,
        tags: payload.tags,
      })
      await workspaceStore.loadKnowledgeTree()
      workspaceStore.showToast('已新增文件并加入图书馆')
    }
    createDialogMode.value = null
    await Promise.all([loadItems(), loadTags()])
  } catch (error) {
    workspaceStore.showToast(`创建失败 — ${errorMessage(error)}`)
  }
}

async function saveEdit(payload: { title: string; description: string; cover_mode: LibraryItem['cover_mode']; cover_asset_id: string; tags: string[] }) {
  if (!editItem.value) return
  await updateLibraryItem(editItem.value.item_id, {
    user_id: settingsStore.profile.userId,
    title: payload.title,
    description: payload.description,
    cover_mode: payload.cover_mode,
    cover_asset_id: payload.cover_asset_id,
    tags: payload.tags,
  })
  editItem.value = null
  await Promise.all([loadItems(), loadTags()])
}

async function removeItem(item: LibraryItem) {
  if (!window.confirm(`移出图书馆: ${item.display_title}? 真实文件不会被删除。`)) return
  await deleteLibraryItem(settingsStore.profile.userId, item.item_id)
  selectedItem.value = null
  await loadItems()
}

async function removeSelected() {
  if (!hasSelection.value) return
  if (!window.confirm(`移出选中的 ${selectedIds.value.size} 项? 真实文件不会被删除。`)) return
  for (const item of selectedItems.value) {
    await deleteLibraryItem(settingsStore.profile.userId, item.item_id)
  }
  selectedIds.value = new Set()
  await loadItems()
}

async function tagSelected() {
  if (!hasSelection.value) return
  const tagText = window.prompt('为选中项设置标签,用英文逗号分隔', '')?.trim()
  if (tagText === undefined) return
  const tags = tagText.split(',').map((tag) => tag.trim()).filter(Boolean)
  for (const item of selectedItems.value) {
    await updateLibraryItem(item.item_id, {
      user_id: settingsStore.profile.userId,
      tags,
    })
  }
  await Promise.all([loadItems(), loadTags()])
}

function relativeUploadedPath(uploadedPath: string, knowledgeDir: string): string {
  const normalizedRoot = knowledgeDir.replace(/\\/g, '/').replace(/\/+$/g, '')
  const normalizedPath = uploadedPath.replace(/\\/g, '/')
  if (normalizedPath.startsWith(`${normalizedRoot}/`)) {
    return normalizedPath.slice(normalizedRoot.length + 1)
  }
  return normalizedPath.split('/').pop() ?? ''
}

function formatDate(raw: string): string {
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.slice(0, 16)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function contentTypeLabel(value: string): string {
  if (value === 'knowledge_file') return '知识库文件'
  if (value === 'web_url') return '网页'
  if (value === 'collection') return '集锦'
  return '全部'
}

function sortLabel(value: string): string {
  if (value === 'source_mtime') return '真实修改日期'
  if (value === 'title') return '图书馆假名'
  if (value === 'source_name') return '真实文件名'
  return '编辑日期'
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请检查后端连接'
}
</script>

<template>
  <section class="library-view">
    <header class="library-toolbar">
      <div class="nav-row">
        <div class="nav-buttons">
          <button class="icon-toolbar-btn" type="button" title="回退" :disabled="!canGoBack" @click="goBack">
            <ArrowLeft :size="16" />
          </button>
          <button class="icon-toolbar-btn" type="button" title="反回退" :disabled="!canGoForward" @click="goForward">
            <ArrowRight :size="16" />
          </button>
          <button class="icon-toolbar-btn" type="button" title="回到上级目录" :disabled="!canGoUp" @click="goUp">
            <ArrowUp :size="16" />
          </button>
          <button class="icon-toolbar-btn" type="button" title="刷新" @click="refreshLibrary">
            <RefreshCw :size="16" />
          </button>
        </div>
        <nav class="path-box" :title="virtualPath">
          <button class="path-segment" type="button" title="图书馆根目录" @click="goBreadcrumb('')">图书馆</button>
          <template v-for="crumb in breadcrumbs" :key="crumb.item_id">
            <span class="path-separator">/</span>
            <button class="path-segment" type="button" :title="crumb.title" @click="goBreadcrumb(crumb.item_id)">
              {{ crumb.title }}
            </button>
          </template>
        </nav>
        <label class="search-box">
          <Search :size="14" />
          <input v-model="query" type="search" placeholder="查找" />
        </label>
        <button class="icon-toolbar-btn" type="button" :title="tagFilterTitle" @click="cycleTagFilter">
          <Tags :size="16" />
        </button>
        <button class="icon-toolbar-btn" type="button" :title="typeFilterTitle" @click="cycleContentTypeFilter">
          <HardDrive :size="16" />
        </button>
        <button class="icon-toolbar-btn" type="button" :title="sortTitle" @click="cycleSortKey">
          <CalendarClock :size="16" />
        </button>
        <button class="icon-toolbar-btn" type="button" :title="sortDirection === 'desc' ? '降序' : '升序'" @click="sortDirection = sortDirection === 'desc' ? 'asc' : 'desc'">
          <ArrowDownUp :size="16" />
        </button>
        <button class="icon-toolbar-btn" type="button" title="新增文件" @click="openCreateBookDialog">
          <FilePlus2 :size="16" />
        </button>
        <button class="icon-toolbar-btn" type="button" title="新增集锦" @click="openCreateCollectionDialog">
          <FolderPlus :size="16" />
        </button>
        <button class="icon-toolbar-btn" :class="{ active: multiSelect }" type="button" title="多选" @click="multiSelect = !multiSelect">
          <Tags :size="16" />
        </button>
        <template v-if="multiSelect">
          <span class="selected-count">{{ selectedIds.size }}</span>
          <button class="icon-toolbar-btn" type="button" title="为选中项设置标签" :disabled="!hasSelection" @click="tagSelected">
            <Tags :size="16" />
          </button>
          <button class="icon-toolbar-btn danger" type="button" title="移出选中项" :disabled="!hasSelection" @click="removeSelected">
            <Trash2 :size="16" />
          </button>
        </template>
      </div>
    </header>

    <section class="library-content">
      <main class="library-body">
        <div v-if="loading" class="empty-state">正在读取图书馆</div>
        <div v-else-if="items.length === 0" class="empty-state">
          当前集锦为空。新增文件或创建集锦后会出现在这里。
        </div>
        <div v-else class="library-grid">
          <LibraryCard
            v-for="item in items"
            :key="item.item_id"
            :item="item"
            :selected="multiSelect ? selectedIds.has(item.item_id) : selectedItem?.item_id === item.item_id"
            :multi-select="multiSelect"
            @open="openItem"
            @edit="editItem = $event"
            @toggle="toggleItem"
            @select="selectItem"
            @drag-start="startDrag"
            @drop-on="dropOnItem"
          />
        </div>
      </main>

      <aside class="detail-drawer" :class="{ open: drawerOpen }">
        <template v-if="selectedItem">
          <header class="drawer-head">
            <div class="drawer-title" :title="selectedItem.display_title">{{ selectedItem.display_title }}</div>
            <button class="icon-toolbar-btn" type="button" title="关闭" @click="selectedItem = null">
              <X :size="15" />
            </button>
          </header>
          <div class="drawer-section">
            <div class="drawer-kv">
              <FolderOpen v-if="selectedItem.item_type === 'collection'" :size="15" />
              <Link v-else-if="selectedItem.content_type === 'web_url'" :size="15" />
              <HardDrive v-else :size="15" />
              <span>{{ selectedItem.item_type === 'collection' ? '集锦' : selectedItem.source_name || selectedItem.source_path }}</span>
            </div>
            <div class="drawer-kv">
              <CalendarClock :size="15" />
              <span>{{ selectedDate || '无日期' }}</span>
            </div>
            <div class="drawer-kv">
              <HardDrive :size="15" />
              <span>{{ selectedItem.item_type === 'collection' ? `${selectedItem.child_count} 项` : `${selectedItem.source_size || 0} bytes` }}</span>
            </div>
          </div>
          <div v-if="selectedItem.description" class="drawer-section">
            <div class="drawer-label">Description</div>
            <p class="drawer-description">{{ selectedItem.description }}</p>
          </div>
          <div v-if="selectedItem.tags.length" class="drawer-section">
            <div class="drawer-label">Tags</div>
            <div class="drawer-tags">
              <span v-for="tag in selectedItem.tags" :key="tag" class="tag-pill">{{ tag }}</span>
            </div>
          </div>
          <div v-if="selectedItem.item_type === 'collection'" class="drawer-section drawer-section-grow">
            <div class="drawer-label">内容</div>
            <div v-if="drawerChildrenLoading" class="drawer-empty">正在读取</div>
            <div v-else-if="drawerChildren.length === 0" class="drawer-empty">空集锦</div>
            <template v-else>
              <button
                v-for="child in drawerChildren"
                :key="child.item_id"
                class="drawer-child"
                type="button"
                :title="child.display_title"
                @click="selectItem(child)"
                @dblclick.stop="openItem(child)"
              >
                <FolderOpen v-if="child.item_type === 'collection'" :size="14" />
                <Link v-else-if="child.content_type === 'web_url'" :size="14" />
                <HardDrive v-else :size="14" />
                <span>{{ child.display_title }}</span>
              </button>
            </template>
          </div>
        </template>
      </aside>
    </section>

    <LibraryItemDialog
      :open="Boolean(editItem)"
      :item="editItem"
      :user-id="settingsStore.profile.userId"
      @close="editItem = null"
      @save="saveEdit"
    />
    <LibraryCreateDialog
      :open="Boolean(createDialogMode)"
      :mode="createDialogMode ?? 'book'"
      :user-id="settingsStore.profile.userId"
      @close="createDialogMode = null"
      @create="createFromDialog"
    />
  </section>
</template>

<style scoped>
.library-view {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
  background: var(--color-canvas);
}

.library-toolbar {
  display: flex;
  align-items: center;
  min-width: 0;
  min-height: 40px;
  padding: 5px 8px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-raised);
}

.nav-row {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: nowrap;
}

.nav-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.icon-toolbar-btn,
.path-segment,
.search-box {
  display: inline-flex;
  align-items: center;
  height: 28px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.icon-toolbar-btn {
  justify-content: center;
  width: 32px;
  padding: 0;
}

.icon-toolbar-btn:hover,
.path-segment:hover {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  color: var(--color-primary);
}

.icon-toolbar-btn.active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.icon-toolbar-btn.danger {
  color: var(--color-danger);
}

.icon-toolbar-btn:disabled {
  opacity: 0.38;
  pointer-events: none;
}

.path-box {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  min-width: 160px;
  height: 28px;
  overflow: hidden;
  border-radius: 6px;
  background: var(--color-canvas);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-border) 55%, transparent);
  padding: 0 6px;
}

.path-segment {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: transparent;
  box-shadow: none;
  padding: 0 7px;
}

.path-separator {
  color: var(--color-text-muted);
  font-size: 12px;
}

.search-box {
  flex: 0 1 220px;
  gap: 6px;
  padding: 0 8px;
  background: var(--color-canvas);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-border) 55%, transparent);
}

.search-box input {
  min-width: 0;
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
}

.selected-count {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 11px;
}

.library-content {
  position: relative;
  display: block;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.library-body {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: auto;
  padding: 16px;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 16px;
  align-items: start;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 260px;
  border-radius: 10px;
  color: var(--color-text-muted);
  background: var(--color-surface);
  text-align: center;
  padding: 24px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.detail-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  width: 300px;
  min-width: 300px;
  overflow: hidden;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  transform: translateX(100%);
  transition:
    transform 240ms ease;
}

.detail-drawer.open {
  transform: translateX(0);
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border-bottom: 1px solid var(--color-border);
}

.drawer-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
}

.drawer-section {
  display: grid;
  gap: 8px;
  padding: 12px;
}

.drawer-section-grow {
  align-content: start;
  max-height: 50%;
  overflow: auto;
}

.drawer-kv {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.drawer-kv span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-label {
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.drawer-description {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.drawer-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.drawer-empty {
  color: var(--color-text-muted);
  font-size: 12px;
}

.drawer-child {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  min-height: 28px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--color-text-secondary);
  padding: 0 7px;
  text-align: left;
}

.drawer-child:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.drawer-child span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  max-width: 180px;
  min-height: 23px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 0 8px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 860px) {
  .search-box {
    flex: 0 1 150px;
  }

  .library-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail-drawer.open {
    width: 260px;
    min-width: 260px;
  }
}
</style>
