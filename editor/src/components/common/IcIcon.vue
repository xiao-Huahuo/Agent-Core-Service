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
}

const svgContent = computed(() => {
  const file = ICON_FILES[props.name]
  if (!file) return ''
  const key = Object.keys(rawIcons).find((path) => path.endsWith(file))
  return key ? rawIcons[key] : ''
})
</script>

<template>
  <span
    class="ic-icon"
    :style="{ fontSize: `${size}px` }"
    :aria-hidden="true"
    v-html="svgContent"
  ></span>
</template>

<style scoped>
.ic-icon {
  display: inline-flex;
  flex: 0 0 auto;
  line-height: 1;
}

.ic-icon :deep(svg) {
  display: block;
  width: 1em;
  height: 1em;
}
</style>
