<!--
  Virtual library bar (compact row) view.

  Usage:
  Render one book or collection as a horizontal bar in the library list.
  Left thumb shows the cover image or a text key; right column stacks
  title + tags, description, then date + child count. Same interaction
  surface (selection, drag, context menu) as LibraryCard.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, FolderOpen, Image as ImageIcon, Link, TriangleAlert } from 'lucide-vue-next'

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
const dateLabel = computed(() => {
  const raw = props.item.source_mtime || props.item.updated_at
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.slice(0, 16)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
})
const badgeText = computed(() => {
  if (isCollection.value) return '集锦'
  if (props.item.content_type === 'web_url') return props.item.source_url
  return props.item.source_name || props.item.source_path || props.item.display_title
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
    class="library-bar"
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
    <button
      v-if="multiSelect"
      class="select-button"
      :class="{ checked: selected }"
      type="button"
      :title="selected ? '取消选择' : '选择'"
      @click.stop="emit('toggle', item)"
    >
      <Check v-if="selected" :size="14" />
    </button>
    <section class="thumb">
      <img v-if="coverUrl" class="thumb-image" :src="coverUrl" alt="" />
      <div v-else-if="item.cover_mode === 'description' && item.description" class="thumb-text">
        {{ item.description }}
      </div>
      <div v-else-if="item.cover_mode === 'title' || isCollection" class="thumb-title">
        {{ item.display_title }}
      </div>
      <div v-else class="thumb-icon">
        <FolderOpen v-if="isCollection" :size="26" />
        <Link v-else-if="item.content_type === 'web_url'" :size="26" />
        <img v-else-if="fileIcon.src" class="thumb-file-icon" :src="fileIcon.src" alt="" />
        <ImageIcon v-else :size="26" />
      </div>
      <TriangleAlert v-if="!item.source_exists" class="missing-icon" :size="14" />
    </section>
    <section class="bar-meta">
      <div class="bar-title-row">
        <FavoriteButton class="bar-favorite" target-type="library_item" :target-id="item.item_id" />
        <span class="bar-type-icon">
          <FolderOpen v-if="isCollection" :size="16" />
          <Link v-else-if="item.content_type === 'web_url'" :size="16" />
          <img v-else-if="fileIcon.src" class="bar-type-file-icon" :src="fileIcon.src" alt="" />
          <ImageIcon v-else :size="16" />
        </span>
        <span class="bar-title" :title="item.display_title">{{ item.display_title }}</span>
        <div class="bar-tag-row">
          <span v-for="tag in item.tags" :key="tag" class="tag-pill" :title="tag">{{ tag }}</span>
        </div>
        <span
          v-if="!multiSelect"
          class="bar-badge"
          :class="{ collection: isCollection }"
          :title="badgeText"
        >{{ badgeText }}</span>
      </div>
      <div class="bar-description" :title="item.description">{{ item.description || '无描述' }}</div>
      <div class="bar-foot">
        <span>{{ dateLabel }}</span>
        <span v-if="isCollection" class="bar-count">{{ item.child_count }} 项</span>
      </div>
    </section>
  </article>
</template>

<style scoped>
.library-bar {
  position: relative;
  display: flex;
  align-items: stretch;
  min-width: 0;
  min-height: 88px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  transition:
    border-color 160ms ease,
    background 160ms ease;
}

.library-bar:hover,
.library-bar.selected {
  background: var(--color-surface-raised);
  border-color: color-mix(in srgb, var(--color-primary) 42%, var(--color-border));
}

.library-bar.selected {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.library-bar.drag-over {
  outline: 2px dashed var(--color-primary);
  outline-offset: 4px;
}

.library-bar.missing {
  outline: 2px solid color-mix(in srgb, var(--color-danger) 72%, transparent);
}

.select-button {
  position: absolute;
  top: 8px;
  right: 8px;
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

.select-button :deep(svg) {
  margin-left: -1px;
}

.select-button.checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.thumb {
  position: relative;
  flex: 0 0 104px;
  min-width: 0;
  overflow: hidden;
  background: var(--color-surface-raised);
}

.thumb-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-text,
.thumb-title,
.thumb-icon {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.thumb-text {
  padding: 10px;
  color: var(--color-text);
  font-size: calc(10px * var(--font-scale));
  line-height: 1.45;
  text-align: center;
  white-space: pre-wrap;
}

.thumb-title {
  padding: 12px;
  color: var(--color-text);
  font-size: calc(14px * var(--font-scale));
  line-height: 1.25;
  font-weight: 700;
  text-align: center;
  overflow-wrap: anywhere;
}

.thumb-icon {
  color: var(--color-text-muted);
}

.thumb-file-icon {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.missing-icon {
  position: absolute;
  right: 6px;
  bottom: 6px;
  color: var(--color-danger);
}

.bar-meta {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  min-width: 0;
  flex: 1 1 auto;
  padding: 10px 12px;
}

.bar-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.bar-favorite {
  margin-left: -4px;
}

.bar-title {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
  color: var(--color-text);
}

.bar-type-icon {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  color: var(--color-text-tertiary);
}

.bar-type-file-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

.bar-tag-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 5px;
  min-width: 0;
  overflow: hidden;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  max-width: 120px;
  min-height: 20px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 0 8px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-badge {
  flex: 0 0 auto;
  margin-left: auto;
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-tertiary);
}

.bar-badge.collection {
  color: var(--color-primary);
  font-weight: 600;
}

.bar-description {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-muted);
}

.bar-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
}

.bar-count {
  flex: 0 0 auto;
  color: var(--color-primary);
  font-weight: 600;
}
</style>
