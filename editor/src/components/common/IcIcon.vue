<!--
  Inline SVG icon component for local Iconify "ic" (Material outlined) icons.

  Usage:
  Icons live in assets/icons/svg/ic and are inlined so their currentColor
  follows the surrounding button/text color. Callers pick by semantic name.
-->
<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'IcIcon' })

const props = withDefaults(defineProps<{
  name: string
  size?: number
}>(), {
  size: 18,
})

const rawIcons = import.meta.glob('@/assets/icons/svg/ic/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const ICON_FILES: Record<string, string> = {
  search: 'ic--outline-search.svg',
  filter: 'ic--outline-filter.svg',
  sort: 'ic--outline-swap-vert.svg',
  unfold: 'ic--outline-unfold-more.svg',
  star: 'ic--outline-star.svg',
  refresh: 'ic--outline-refresh.svg',
  history: 'ic--outline-history.svg',
  'new-folder': 'ic--outline-create-new-folder.svg',
  'new-file': 'ic--outline-note-add.svg',
  back: 'ic--outline-arrow-left.svg',
  'arrow-left': 'ic--outline-arrow-back.svg',
  check: 'ic--outline-check.svg',
  close: 'ic--outline-close.svg',
  'arrow-up': 'ic--outline-arrow-upward.svg',
  'arrow-down': 'ic--outline-arrow-downward.svg',
  'folder-open': 'ic--outline-folder-open.svg',
  git: 'ic--outline-account-tree.svg',
  todo: 'ic--outline-check-box.svg',
  graph: 'ic--outline-bubble-chart.svg',
  ingest: 'ic--outline-storage.svg',
  'arrow-right': 'ic--outline-arrow-forward.svg',
  'multi-select': 'ic--outline-checklist.svg',
  trash: 'ic--outline-delete.svg',
  document: 'ic--outline-description.svg',
  folder: 'ic--outline-folder.svg',
  book: 'ic--outline-menu-book.svg',
  code: 'ic--outline-code.svg',
  'auto-awesome': 'ic--outline-auto-awesome.svg',
  dashboard: 'ic--outline-space-dashboard.svg',
  feedback: 'ic--outline-feedback.svg',
  bug: 'ic--outline-bug-report.svg',
  settings: 'ic--outline-settings.svg',
  upload: 'ic--outline-upload.svg',
  'cloud-upload': 'ic--outline-cloud-upload.svg',
  'chevron-right': 'ic--outline-chevron-right.svg',
  'chevron-down': 'ic--outline-expand-more.svg',
  'unfold-less': 'ic--outline-unfold-less.svg',
  add: 'ic--outline-add.svg',
  replay: 'ic--outline-replay.svg',
  warning: 'ic--outline-warning.svg',
  image: 'ic--outline-image.svg',
  link: 'ic--outline-link.svg',
  cancel: 'ic--outline-cancel.svg',
  'add-photo': 'ic--outline-add-photo-alternate.svg',
  language: 'ic--outline-language.svg',
  save: 'ic--outline-save.svg',
  label: 'ic--outline-label.svg',
  'view-stream': 'ic--outline-view-stream.svg',
  'grid-view': 'ic--outline-grid-view.svg',
  event: 'ic--outline-event.svg',
  info: 'ic--outline-info.svg',
  psychology: 'ic--outline-psychology.svg',
  'radio-unchecked': 'ic--outline-radio-button-unchecked.svg',
  spinner: 'ic--outline-autorenew.svg',
  layers: 'ic--outline-layers.svg',
  'view-list': 'ic--outline-view-list.svg',
  tune: 'ic--outline-tune.svg',
  'center-focus': 'ic--outline-center-focus-strong.svg',
  play: 'ic--outline-play-arrow.svg',
  pause: 'ic--outline-pause.svg',
  'text-fields': 'ic--outline-text-fields.svg',
  block: 'ic--outline-block.svg',
  'error-outline': 'ic--outline-error-outline.svg',
  'check-circle': 'ic--outline-check-circle.svg',
  download: 'ic--outline-download.svg',
  edit: 'ic--outline-edit.svg',
  visibility: 'ic--outline-visibility.svg',
  'view-column': 'ic--outline-view-column.svg',
  group: 'ic--outline-group.svg',
  'add-comment': 'ic--outline-add-comment.svg',
  forum: 'ic--outline-forum.svg',
  'open-in-full': 'ic--outline-open-in-full.svg',
  schedule: 'ic--outline-schedule.svg',
  copy: 'ic--outline-content-copy.svg',
  'thumb-up': 'ic--outline-thumb-up.svg',
  'thumb-down': 'ic--outline-thumb-down.svg',
  'open-in-new': 'ic--outline-open-in-new.svg',
  'more-horiz': 'ic--outline-more-horiz.svg',
  'view-sidebar': 'ic--outline-view-sidebar.svg',
  shield: 'ic--outline-gpp-good.svg',
  stop: 'ic--outline-stop.svg',
  send: 'ic--outline-send.svg',
  build: 'ic--outline-build.svg',
  'fact-check': 'ic--outline-fact-check.svg',
  'file': 'ic--outline-insert-drive-file.svg',
  archive: 'ic--outline-archive.svg',
  'edit-note': 'ic--outline-edit-note.svg',
  'table-chart': 'ic--outline-table-chart.svg',
  title: 'ic--outline-title.svg',
  'manage-search': 'ic--outline-manage-search.svg',
  hub: 'ic--outline-hub.svg',
  checklist: 'ic--outline-checklist.svg',
  calendar: 'ic--outline-calendar-today.svg',
  cut: 'ic--outline-content-cut.svg',
  paste: 'ic--outline-content-paste.svg',
  remove: 'ic--outline-remove.svg',
}

const svgInner = computed(() => {
  const file = ICON_FILES[props.name]
  if (!file) return ''
  const key = Object.keys(rawIcons).find((path) => path.endsWith(file))
  const raw = key ? rawIcons[key] : ''
  // 只注入 <svg> 内部内容,根元素由本组件渲染为真实 svg 标签,
  // 使 class/其他 attrs 直接透传到 svg 根,与 lucide 组件 DOM 一致
  const m = raw.match(/<svg[^>]*>([\s\S]*)<\/svg>/)
  return m ? m[1] : raw
})
</script>

<template>
  <svg
    class="ic-icon"
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 24 24"
    fill="currentColor"
    :style="{ fontSize: `${size}px` }"
    :aria-hidden="true"
    v-html="svgInner"
  ></svg>
</template>

<style scoped>
.ic-icon {
  display: block;
  flex: 0 0 auto;
  width: 1em;
  height: 1em;
}
</style>
