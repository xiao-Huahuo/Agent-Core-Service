/** Global appearance background application tests. */

import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSettingsStore } from '@/stores/settings'

describe('settings appearance background', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-app-background-cover')
    document.documentElement.style.removeProperty('--app-background-image')
    setActivePinia(createPinia())
  })

  it('applies and resets a persisted library asset URL', () => {
    const store = useSettingsStore()

    store.updateProfile({ backgroundCoverUrl: '/library/assets/u1/cover.png' })
    expect(document.documentElement.getAttribute('data-app-background-cover')).toBe('true')
    expect(document.documentElement.style.getPropertyValue('--app-background-image')).toContain('/library/assets/u1/cover.png')

    store.updateProfile({ backgroundCoverUrl: '' })
    expect(document.documentElement.hasAttribute('data-app-background-cover')).toBe(false)
    expect(document.documentElement.style.getPropertyValue('--app-background-image')).toBe('')
  })

})
