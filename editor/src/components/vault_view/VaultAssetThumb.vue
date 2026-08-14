<!--
  Vault asset thumbnail.

  Usage:
  Receives a vault token and asset id, fetches the protected asset as a blob URL
  for the current unlock session, then revokes the URL when the thumbnail changes
  or unmounts.
-->
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import { fetchVaultAssetUrl } from '@/api/vault'
import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'VaultAssetThumb' })

const props = defineProps<{
  token: string
  assetId: string
  fallbackIcon: string
}>()

const objectUrl = ref('')

watch(
  () => [props.token, props.assetId] as const,
  async () => {
    revokeObjectUrl()
    if (!props.token || !props.assetId) return
    try {
      objectUrl.value = await fetchVaultAssetUrl(props.token, props.assetId)
    } catch {
      objectUrl.value = ''
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  revokeObjectUrl()
})

function revokeObjectUrl() {
  if (!objectUrl.value) return
  URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = ''
}
</script>

<template>
  <img v-if="objectUrl" class="asset-thumb" :src="objectUrl" alt="" />
  <span v-else class="type-icon" aria-hidden="true">
    <IcIcon :name="fallbackIcon" :size="18" />
  </span>
</template>

<style scoped>
.asset-thumb,
.type-icon {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.asset-thumb {
  object-fit: cover;
  background: var(--color-surface-raised);
}

.type-icon {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
</style>
