/** Independent UI and editor text font-size store tests. */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useSettingsStore } from '@/stores/settings'

describe('settings font sizes', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('style')
    setActivePinia(createPinia())
  })

  it('applies UI and editor text scales through separate CSS variables', () => {
    const store = useSettingsStore()

    store.setUiFontSizePercent(90)
    store.setTextFontSizePercent(125)

    expect(document.documentElement.style.getPropertyValue('--font-scale')).toBe('1.08')
    expect(document.documentElement.style.getPropertyValue('--text-font-scale')).toBe('1.95')
  })
})
