/*
 * User favorite state store.
 *
 * Usage:
 * Keeps a frontend cache of backend-persisted favorites. All mutations call the
 * /favorites API first; this store does not use browser storage for business
 * persistence.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  addFavorite,
  deleteFavorite,
  listFavorites,
  type FavoriteRecord,
  type FavoriteTargetType,
} from '@/api/favorites'
import { useSettingsStore } from '@/stores/settings'

type FavoriteKey = `${FavoriteTargetType}:${string}:${string}`

function buildKey(targetType: FavoriteTargetType, targetId: string, libraryId = ''): FavoriteKey {
  return `${targetType}:${libraryId}:${targetId}`
}

export const useFavoritesStore = defineStore('favorites', () => {
  const records = ref<FavoriteRecord[]>([])
  const loading = ref(false)
  const pendingKeys = ref<Set<FavoriteKey>>(new Set())

  const recordMap = computed(() => {
    const map = new Map<FavoriteKey, FavoriteRecord>()
    for (const record of records.value) {
      map.set(buildKey(record.target_type, record.target_id, record.library_id), record)
    }
    return map
  })

  function activeLibraryId(): string {
    const settingsStore = useSettingsStore()
    return settingsStore.activeKnowledgeLibrary?.libraryId || settingsStore.profile.activeLibraryId || ''
  }

  function scopeFor(targetType: FavoriteTargetType, libraryId?: string): string {
    return targetType === 'session' ? '' : (libraryId ?? activeLibraryId())
  }

  function isFavorite(targetType: FavoriteTargetType, targetId: string, libraryId?: string): boolean {
    return recordMap.value.has(buildKey(targetType, targetId, scopeFor(targetType, libraryId)))
  }

  function isPending(targetType: FavoriteTargetType, targetId: string, libraryId?: string): boolean {
    return pendingKeys.value.has(buildKey(targetType, targetId, scopeFor(targetType, libraryId)))
  }

  function idsFor(targetType: FavoriteTargetType, libraryId?: string): Set<string> {
    const scope = scopeFor(targetType, libraryId)
    return new Set(
      records.value
        .filter((record) => record.target_type === targetType && record.library_id === scope)
        .map((record) => record.target_id),
    )
  }

  async function load(userId: string, targetType?: FavoriteTargetType, libraryId?: string | null): Promise<void> {
    if (!userId) return
    loading.value = true
    try {
      const response = await listFavorites({
        userId,
        targetType,
        libraryId: targetType === 'session' ? '' : libraryId,
      })
      const incoming = response.favorites
      if (!targetType) {
        records.value = incoming
        return
      }
      const libraryFiltered = libraryId !== null && libraryId !== undefined
      records.value = [
        ...records.value.filter((record) => {
          if (record.target_type !== targetType) return true
          if (libraryFiltered) return record.library_id !== (libraryId ?? '')
          return false
        }),
        ...incoming,
      ]
    } finally {
      loading.value = false
    }
  }

  async function toggle(targetType: FavoriteTargetType, targetId: string, libraryId?: string): Promise<void> {
    const settingsStore = useSettingsStore()
    const userId = settingsStore.profile.userId
    if (!userId || !targetId) return
    const scope = scopeFor(targetType, libraryId)
    const key = buildKey(targetType, targetId, scope)
    if (pendingKeys.value.has(key)) return
    pendingKeys.value = new Set([...pendingKeys.value, key])
    try {
      if (recordMap.value.has(key)) {
        await deleteFavorite({
          user_id: userId,
          library_id: scope,
          target_type: targetType,
          target_id: targetId,
        })
        records.value = records.value.filter((record) => buildKey(record.target_type, record.target_id, record.library_id) !== key)
        return
      }
      const record = await addFavorite({
        user_id: userId,
        library_id: scope,
        target_type: targetType,
        target_id: targetId,
      })
      records.value = [
        record,
        ...records.value.filter((item) => buildKey(item.target_type, item.target_id, item.library_id) !== key),
      ]
    } finally {
      const next = new Set(pendingKeys.value)
      next.delete(key)
      pendingKeys.value = next
    }
  }

  return {
    records,
    loading,
    load,
    isFavorite,
    isPending,
    idsFor,
    toggle,
    activeLibraryId,
  }
})
