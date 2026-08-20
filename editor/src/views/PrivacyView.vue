<!--
  Privacy page.

  Usage:
  Reuses the FavoritesView shell and its file/library components while locking
  privacy filters on and limiting navigation to the two requested child pages.
-->
<script setup lang="ts">
import FavoritesView from '@/views/FavoritesView.vue'

defineOptions({ name: 'PrivacyView' })
</script>

<template>
  <FavoritesView privacy-mode />
</template>
