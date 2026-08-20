/*
 * Backend-persisted privacy state store.
 *
 * Usage:
 * Shared privacy buttons and filtered pages read this cache; every mutation is
 * committed through /privacy before the local record set changes.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { addPrivacy, deletePrivacy, listPrivacy, type PrivacyRecord, type PrivacyTargetType } from '@/api/privacy'
import { useSettingsStore } from '@/stores/settings'

type PrivacyKey = `${PrivacyTargetType}:${string}:${string}`

function buildKey(targetType: PrivacyTargetType, targetId: string, libraryId: string): PrivacyKey {
  return `${targetType}:${libraryId}:${targetId}`
}

export const usePrivacyStore = defineStore('privacy', () => {
  const records = ref<PrivacyRecord[]>([])
  const loading = ref(false)
  const loadedScopeKeys = ref<Set<PrivacyKey>>(new Set())
  const pendingKeys = ref<Set<PrivacyKey>>(new Set())
  const recordMap = computed(() => new Map(records.value.map((record) => [
    buildKey(record.target_type, record.target_id, record.library_id),
    record,
  ])))

  function activeLibraryId(): string {
    const settingsStore = useSettingsStore()
    return settingsStore.activeKnowledgeLibrary?.libraryId || settingsStore.profile.activeLibraryId || ''
  }

  function scope(libraryId?: string): string {
    return libraryId ?? activeLibraryId()
  }

  function isPrivate(targetType: PrivacyTargetType, targetId: string, libraryId?: string): boolean {
    return recordMap.value.has(buildKey(targetType, targetId, scope(libraryId)))
  }

  function isPending(targetType: PrivacyTargetType, targetId: string, libraryId?: string): boolean {
    return pendingKeys.value.has(buildKey(targetType, targetId, scope(libraryId)))
  }

  function idsFor(targetType: PrivacyTargetType, libraryId?: string): Set<string> {
    const libraryScope = scope(libraryId)
    return new Set(records.value
      .filter((record) => record.target_type === targetType && record.library_id === libraryScope)
      .map((record) => record.target_id))
  }

  function hasLoaded(targetType: PrivacyTargetType, libraryId?: string): boolean {
    return loadedScopeKeys.value.has(buildKey(targetType, '', scope(libraryId)))
  }

  async function load(userId: string, targetType?: PrivacyTargetType, libraryId?: string | null): Promise<void> {
    if (!userId) return
    loading.value = true
    try {
      const response = await listPrivacy({ userId, targetType, libraryId })
      if (!targetType) {
        records.value = response.privacy
        const nextLoaded = new Set(loadedScopeKeys.value)
        for (const record of response.privacy) {
          nextLoaded.add(buildKey(record.target_type, '', record.library_id))
        }
        loadedScopeKeys.value = nextLoaded
        return
      }
      const filteredLibrary = libraryId !== null && libraryId !== undefined
      records.value = [
        ...records.value.filter((record) => record.target_type !== targetType || (filteredLibrary && record.library_id !== (libraryId ?? ''))),
        ...response.privacy,
      ]
      loadedScopeKeys.value = new Set([
        ...loadedScopeKeys.value,
        buildKey(targetType, '', libraryId ?? activeLibraryId()),
      ])
    } finally {
      loading.value = false
    }
  }

  async function toggle(targetType: PrivacyTargetType, targetId: string, libraryId?: string): Promise<void> {
    const userId = useSettingsStore().profile.userId
    if (!userId || !targetId) return
    const libraryScope = scope(libraryId)
    const key = buildKey(targetType, targetId, libraryScope)
    if (pendingKeys.value.has(key)) return
    pendingKeys.value = new Set([...pendingKeys.value, key])
    try {
      if (recordMap.value.has(key)) {
        await deletePrivacy({ user_id: userId, library_id: libraryScope, target_type: targetType, target_id: targetId })
        records.value = records.value.filter((record) => buildKey(record.target_type, record.target_id, record.library_id) !== key)
        return
      }
      const record = await addPrivacy({ user_id: userId, library_id: libraryScope, target_type: targetType, target_id: targetId })
      records.value = [record, ...records.value.filter((item) => buildKey(item.target_type, item.target_id, item.library_id) !== key)]
    } finally {
      const next = new Set(pendingKeys.value)
      next.delete(key)
      pendingKeys.value = next
    }
  }

  return { records, loading, load, isPrivate, isPending, idsFor, hasLoaded, toggle, activeLibraryId }
})
