<!--
  Drawing-script image or text cover.

  Usage:
  Reused by component cards and details. A persisted image wins; otherwise the
  component title is rendered with the same title-cover principle as LibraryCard.
-->
<script setup lang="ts">
import type { ComponentLibraryItem } from '@/types/componentLibrary'

defineOptions({ name: 'DrawingScriptCover' })

defineProps<{ item: ComponentLibraryItem }>()
</script>

<template>
  <div class="drawing-script-cover" :class="{ 'has-image': item.cover_asset?.url }">
    <img
      v-if="item.cover_asset?.url"
      class="drawing-cover-image"
      :src="item.cover_asset.url"
      :alt="`${item.title} 封面`"
    />
    <strong v-else class="drawing-title-cover">{{ item.title }}</strong>
  </div>
</template>

<style scoped>
.drawing-script-cover {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 0;
  place-items: center;
  overflow: hidden;
  background:
    linear-gradient(145deg, var(--color-primary-softer), transparent 58%),
    var(--color-surface-raised);
}

.drawing-script-cover.has-image {
  background: var(--color-surface-raised);
}

.drawing-cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.drawing-title-cover {
  max-width: 78%;
  color: var(--color-text);
  font-size: calc(24px * var(--font-scale));
  line-height: 1.2;
  text-align: center;
  overflow-wrap: anywhere;
}
</style>
