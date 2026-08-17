/** Right-side browser workspace-state regression tests. */

import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useWorkspaceStore } from '@/stores/workspace'

describe('workspace browser sidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens at the requested URL and toggles without discarding it', () => {
    const store = useWorkspaceStore()

    store.openBrowserSidebar('https://example.com/article')
    expect(store.browserSidebarOpen).toBe(true)
    expect(store.browserSidebarUrl).toBe('https://example.com/article')
    expect(store.browserSidebarNavigationId).toBe(1)

    store.openBrowserSidebar('https://example.com/article')
    expect(store.browserSidebarNavigationId).toBe(2)

    store.toggleBrowserSidebar()
    expect(store.browserSidebarOpen).toBe(false)
    expect(store.browserSidebarUrl).toBe('https://example.com/article')
  })
})
