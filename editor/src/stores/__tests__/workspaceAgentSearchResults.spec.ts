/** Agent-mounted search-result navigation tests. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useWorkspaceStore } from '@/stores/workspace'
import type { SearchSource, UnifiedSearchResult } from '@/types/unifiedSearch'

function result(source: SearchSource, item: Record<string, unknown> = {}): UnifiedSearchResult {
  return {
    id: `${source}-1`, source, title: source, snippet: '', locator: `${source}/1`, updated_at: '',
    score: 1, matched_modes: ['title'], item,
  }
}

describe('workspace Agent search-result navigation', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('opens blocks from the Agent page in the shared search-result sidebar', async () => {
    const store = useWorkspaceStore()
    const target = result('library')

    await store.openAgentSearchResult(target, false)

    expect(store.editorSidebarOpen).toBe(true)
    expect(store.searchSidebarResult).toEqual(target)
  })

  it('routes sidebar-Agent blocks into each owning main library and exact item', async () => {
    const store = useWorkspaceStore()
    const library = result('library', { item_id: 'book-1', parent_id: 'collection-1' })
    await store.openAgentSearchResult(library, true)
    expect(store.mainView).toBe('library')
    expect(store.pendingMainSearchResult).toEqual(library)

    const component = result('components', { component_id: 'cards/a.vue' })
    await store.openAgentSearchResult(component, true)
    expect(store.mainView).toBe('component-library')
    expect(store.pendingMainSearchResult).toEqual(component)

    await store.openAgentSearchResult(result('literature', { form_id: 'form-1', row_id: 'row-1' }), true)
    expect(store.mainView).toBe('literature-reading')
    expect(store.pendingLiteratureEntry).toEqual({ formId: 'form-1', rowId: 'row-1' })

    await store.openAgentSearchResult(result('files', { name: 'a.md', path: 'docs/a.md', isDir: false }), true)
    expect(store.mainView).toBe('editor')
    expect(store.selectedPath).toBe('docs/a.md')
  })
})
