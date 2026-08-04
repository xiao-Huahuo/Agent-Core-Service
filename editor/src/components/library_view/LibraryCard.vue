<!--
  Virtual library large-icon card.

  Usage:
  Render one book or collection in the library grid. The card supports selection,
  double-click opening, and drag-moving items into collection cards.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { buildApiUrl } from '@/api/client'
import FavoriteButton from '@/components/common/FavoriteButton.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import type { LibraryItem } from '@/types/knowledge'

const props = defineProps<{
  item: LibraryItem
  selected: boolean
  multiSelect: boolean
}>()

const emit = defineEmits<{
  open: [item: LibraryItem]
  edit: [item: LibraryItem]
  toggle: [item: LibraryItem]
  select: [item: LibraryItem]
  contextmenu: [event: MouseEvent, item: LibraryItem]
  dragStart: [item: LibraryItem]
  dropOn: [item: LibraryItem]
}>()

const dragOver = ref(false)
const isCollection = computed(() => props.item.item_type === 'collection')
const fileIcon = computed(() => materialFileIconForNode({
  name: props.item.source_name || props.item.display_title,
  path: props.item.source_path || props.item.source_name,
  isDir: isCollection.value,
}))
const coverUrl = computed(() => {
  if (props.item.cover_mode === 'image' && props.item.cover_asset?.url) {
    return props.item.cover_asset.url
  }
  if (props.item.cover_mode === 'source_image' && props.item.source_path) {
    return buildApiUrl('/knowledge/files/raw', {
      user_id: props.item.user_id,
      path: props.item.source_path,
    })
  }
  return ''
})
const sourceLabel = computed(() => {
  if (isCollection.value) return '集锦'
  if (props.item.content_type === 'web_url') return props.item.source_url
  return props.item.source_name || props.item.source_path || '未关联真实内容'
})
const dateLabel = computed(() => {
  const raw = props.item.source_mtime || props.item.updated_at
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.slice(0, 16)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
})
const statusText = computed(() => {
  if (isCollection.value) return `${props.item.child_count} 项`
  const parts = [
    props.item.index_status ? `入库 ${props.item.index_status}` : '未入库',
    props.item.graph_status ? `图谱 ${props.item.graph_status}` : '无图谱',
  ]
  return parts.join(' / ')
})

function handleClick() {
  if (props.multiSelect) {
    emit('toggle', props.item)
    return
  }
  emit('select', props.item)
}

function handleDragStart(event: DragEvent) {
  event.dataTransfer?.setData('text/plain', props.item.item_id)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
  emit('dragStart', props.item)
}

function handleDragOver(event: DragEvent) {
  if (!isCollection.value) return
  event.preventDefault()
  dragOver.value = true
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

function handleDrop(event: DragEvent) {
  if (!isCollection.value) return
  event.preventDefault()
  dragOver.value = false
  emit('dropOn', props.item)
}
</script>

<template>
  <article
    class="library-card"
    :class="{ selected, missing: !item.source_exists, 'drag-over': dragOver, collection: isCollection }"
    draggable="true"
    @click="handleClick"
    @dblclick.stop="emit('open', item)"
    @contextmenu.prevent="emit('contextmenu', $event, item)"
    @dragstart="handleDragStart"
    @dragover="handleDragOver"
    @dragleave="dragOver = false"
    @drop="handleDrop"
  >
    <header v-if="isCollection" class="collection-corner">
      集锦
    </header>
    <FavoriteButton class="library-favorite" target-type="library_item" :target-id="item.item_id" />
    <button
      v-if="multiSelect"
      class="select-button"
      :class="{ checked: selected }"
      type="button"
      :title="selected ? '取消选择' : '选择'"
      @click.stop="emit('toggle', item)"
    >
      <IcIcon v-if="selected" name="check" :size="14" />
    </button>
    <section class="cover">
      <img v-if="coverUrl" class="cover-image" :src="coverUrl" alt="" />
      <div v-else-if="item.cover_mode === 'description' && item.description" class="text-cover">
        {{ item.description }}
      </div>
      <div v-else-if="item.cover_mode === 'title' || isCollection" class="title-cover">
        {{ item.display_title }}
      </div>
      <div v-else class="icon-cover">
        <IcIcon v-if="isCollection" name="folder-open" :size="52" />
        <IcIcon v-else-if="item.content_type === 'web_url'" name="link" :size="52" />
        <img v-else-if="fileIcon.src" class="file-icon" :src="fileIcon.src" alt="" />
        <IcIcon v-else name="image" :size="52" />
      </div>
      <IcIcon v-if="!item.source_exists" name="warning" class="missing-icon" :size="18" />
    </section>
    <section class="meta">
      <div class="tag-row">
        <span v-for="tag in item.tags" :key="tag" class="tag-pill" :title="tag">{{ tag }}</span>
      </div>
      <div class="title" :title="item.display_title">{{ item.display_title }}</div>
      <div v-if="!isCollection" class="source" :title="sourceLabel">
        <img v-if="fileIcon.src" class="source-icon" :src="fileIcon.src" alt="" />
        <IcIcon v-else-if="item.content_type === 'web_url'" name="link" :size="13" />
        <span>{{ sourceLabel }}</span>
      </div>
      <div class="description" :title="item.description">{{ item.description || '无描述' }}</div>
      <div class="foot">
        <span>{{ dateLabel }}</span>
        <span>{{ statusText }}</span>
      </div>
    </section>
  </article>
</template>

<style scoped>
.library-card {
  position: relative;
  display: grid;
  grid-template-rows: 5fr 5fr;
  aspect-ratio: 2 / 3;
  min-width: 0;
  overflow: hidden;
  border: 0;
  border-radius: 18px;
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.10);
  transition:
    box-shadow 160ms ease,
    transform 160ms ease,
    background 160ms ease;
}

.library-card:hover,
.library-card.selected {
  background: var(--color-surface-raised);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.16);
  transform: translateY(-1px);
}

.library-card.selected {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.library-card.drag-over {
  outline: 2px dashed var(--color-primary);
  outline-offset: 4px;
}

.library-card.missing {
  outline: 2px solid color-mix(in srgb, var(--color-danger) 72%, transparent);
}

.collection-corner {
  position: absolute;
  z-index: 3;
  pointer-events: none;
  top: 10px;
  left: -28px;
  transform: rotate(-45deg);
  padding: 3px 36px;
  background: var(--color-collection-corner);
  color: #fff;
  font-size: calc(12px * var(--font-scale));
  font-weight: 700;
  white-space: nowrap;
}


.select-button {
  position: absolute;
  top: 10px;
  right: 40px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.18);
  cursor: pointer;
}

.library-favorite {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 4;
  background: var(--color-canvas);
}

.select-button :deep(svg) {
  margin-left: -1px;
}

.select-button.checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.cover {
  position: relative;
  min-height: 0;
  overflow: hidden;
  background: var(--color-surface-raised);
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.text-cover,
.title-cover,
.icon-cover {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
}

.text-cover {
  padding: 18px;
  color: var(--color-text);
  line-height: 1.55;
  overflow: hidden;
  white-space: pre-wrap;
}

.title-cover {
  padding: 22px;
  color: var(--color-text);
  font-size: calc(22px * var(--font-scale));
  line-height: 1.25;
  font-weight: 700;
  text-align: center;
  overflow-wrap: anywhere;
}

.icon-cover {
  color: var(--color-text-muted);
}

.file-icon {
  width: 64px;
  height: 64px;
  object-fit: contain;
}

.missing-icon {
  position: absolute;
  right: 10px;
  bottom: 10px;
  color: var(--color-danger);
}

.meta {
  display: grid;
  grid-template-rows: minmax(24px, auto) 24px 22px minmax(32px, 1fr) 20px;
  min-height: 0;
  padding: 10px 12px 12px;
  gap: 5px;
}

.library-card.collection .meta {
  grid-template-rows: minmax(24px, auto) 22px minmax(32px, 1fr) 20px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
  min-height: 24px;
  overflow: hidden;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  max-width: 118px;
  min-height: 22px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 0 8px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title,
.source,
.description,
.foot {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.title,
.source,
.foot {
  white-space: nowrap;
}

.title {
  font-weight: 700;
  color: var(--color-text);
}

.source {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-secondary);
}

.source-icon {
  width: 14px;
  height: 14px;
  object-fit: contain;
  flex: 0 0 auto;
}

.description {
  display: -webkit-box;
  color: var(--color-text-muted);
  line-height: 1.4;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.foot {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
}
</style>
