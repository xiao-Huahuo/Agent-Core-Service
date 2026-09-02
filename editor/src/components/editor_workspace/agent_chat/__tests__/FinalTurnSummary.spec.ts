/*
 * Final turn summary tests.
 *
 * Usage:
 * Confirms a completed turn presents persisted file changes and can switch to
 * sources without bringing back the removed summary header.
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import FinalTurnSummary from '../FinalTurnSummary.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { SearchSource, UnifiedSearchResult } from '@/types/unifiedSearch'

describe('FinalTurnSummary', () => {
  it('switches between changes and sources with the panel toggle', async () => {
    const wrapper = mount(FinalTurnSummary, {
      props: {
        sources: [{ source_uri: 'notes/a.md', content: 'A', citation_id: 'K1' }],
        changeSnapshot: {
          snapshot_id: 'snap_1', session_id: 's1', run_id: 'run_1', created_at: '',
          additions: 3, deletions: 2, is_undone: false, edits: [], files: [{ path: 'notes/a.md', additions: 3, deletions: 2, edits: [] }],
        },
      },
      global: {
        stubs: { KnowledgeSources: { props: { defaultExpanded: Boolean }, template: '<div class="stub-sources">{{ defaultExpanded }}</div>' } },
      },
    })

    expect(wrapper.classes()).toContain('final-turn-summary')
    expect(wrapper.find('.summary-header').exists()).toBe(false)
    expect(wrapper.find('.panel-switch').exists()).toBe(true)
    expect(wrapper.text()).toContain('已编辑 1 个文件')
    expect(wrapper.text()).toContain('+3')
    expect(wrapper.text()).toContain('-2')
    expect(wrapper.find('.undo-button .ic-icon').exists()).toBe(true)
    expect(wrapper.find('.stub-sources').exists()).toBe(false)

    await wrapper.findAll('.panel-switch-button')[1]?.trigger('click')

    expect(wrapper.find('.change-summary').exists()).toBe(false)
    expect(wrapper.find('.stub-sources').exists()).toBe(true)
    expect(wrapper.find('.stub-sources').text()).toBe('true')
  })

  it('shows only one changed file in compact sidebar mode', () => {
    const files = ['a.md', 'b.md', 'c.md', 'd.md'].map((path) => ({ path, additions: 1, deletions: 0, edits: [] }))
    const wrapper = mount(FinalTurnSummary, {
      props: {
        compact: true,
        sources: [],
        changeSnapshot: {
          snapshot_id: 'snap_2', session_id: 's1', run_id: 'run_2', created_at: '',
          additions: 4, deletions: 0, is_undone: false, edits: [], files,
        },
      },
    })

    expect(wrapper.classes()).toContain('compact')
    expect(wrapper.findAll('.change-file-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('再显示 3 个文件')
  })

  it('opens local and four-library sources in the shared right editor sidebar', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkspaceStore()
    const node = { name: 'source.md', path: 'notes/source.md', isDir: false }
    const libraryResult = {
      id: 'book-1', source: 'library' as const, title: '知识手册', snippet: '', locator: 'book-1',
      updated_at: '', score: 1, matched_modes: ['title' as const], item: { item_id: 'book-1' },
    }
    store.tree = [node]
    store.mainView = 'agent'
    const openEditorSidebar = vi.spyOn(store, 'openEditorSidebar').mockResolvedValue()
    const openSearchResultSidebar = vi.spyOn(store, 'openSearchResultSidebar').mockResolvedValue()

    const wrapper = mount(FinalTurnSummary, {
      props: {
        sources: [
          { source_uri: 'notes/source.md', content: 'A', citation_id: 'K1' },
          { source_uri: 'library://book-1', content: 'B', citation_id: 'K2', search_result: libraryResult },
        ],
      },
      global: { plugins: [pinia] },
    })

    await wrapper.get('.source-item').trigger('click')
    await wrapper.findAll('.source-item')[1]?.trigger('click')

    expect(openEditorSidebar).toHaveBeenCalledWith(node)
    expect(openSearchResultSidebar).toHaveBeenCalledWith(libraryResult)
    expect(store.mainView).toBe('agent')
  })

  it('opens four-library K sources through their native result sidebars', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkspaceStore()
    const openSearchResultSidebar = vi.spyOn(store, 'openSearchResultSidebar').mockResolvedValue()
    const sources: SearchSource[] = ['files', 'library', 'components', 'literature']
    const sourceItems = sources.map((source, index) => {
      const searchResult: UnifiedSearchResult = {
        id: `${source}-1`, source, title: source, snippet: '',
        locator: source === 'library' ? 'https://example.com/library-1' : `${source}/1`, updated_at: '',
        score: 1, matched_modes: ['title'], item: {},
      }
      return {
        source_uri: searchResult.locator,
        content: source,
        citation_id: `K${index + 1}`,
        search_result: searchResult,
      }
    })
    const wrapper = mount(FinalTurnSummary, {
      props: { sources: sourceItems },
      global: { plugins: [pinia] },
    })

    for (const source of wrapper.findAll('.source-item')) await source.trigger('click')

    expect(openSearchResultSidebar.mock.calls.map(([result]) => result.source)).toEqual(sources)
  })
})
