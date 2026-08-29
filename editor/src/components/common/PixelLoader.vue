<!--
  Shared five-bar pixel loader.

  Usage:
  Use for compact ongoing work indicators in smart-table cells, model banners,
  and the TopCommandBar model activity shortcut.
-->
<script setup lang="ts">
defineOptions({ name: 'PixelLoader' })
</script>

<template>
  <span class="pixel-loader" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
</template>

<style scoped>
.pixel-loader {
  display: grid;
  grid-template-columns: repeat(5, 5px);
  gap: 3px;
  height: 13px;
  align-items: end;
}

.pixel-loader i {
  display: block;
  width: 5px;
  height: 5px;
  background: var(--color-primary);
  image-rendering: pixelated;
  animation: smart-pixel-loader 800ms steps(2, end) infinite;
}

.pixel-loader i:nth-child(2),
.pixel-loader i:nth-child(4) { animation-delay: 120ms; }
.pixel-loader i:nth-child(3) { animation-delay: 240ms; }

@keyframes smart-pixel-loader {
  0%, 100% { height: 5px; opacity: 0.38; }
  50% { height: 13px; opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .pixel-loader i { animation: none; opacity: 0.75; }
}
</style>
