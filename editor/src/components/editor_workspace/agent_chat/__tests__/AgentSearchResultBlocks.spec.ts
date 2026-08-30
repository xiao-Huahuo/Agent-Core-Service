/** Agent-mounted four-library result block tests. */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AgentSearchResultBlocks from '@/components/editor_workspace/agent_chat/AgentSearchResultBlocks.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { SearchSource, UnifiedSearchResult } from '@/types/unifiedSearch'

function result(source: SearchSource): UnifiedSearchResult {
  return {
    id: `${source}-1`, source, title: source, snippet: '', locator: `${source}/1`, updated_at: '',
    score: 1, matched_modes: ['title'], item: { item_id: `${source}-1` },
  }
}

describe('AgentSearchResultBlocks', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders every result through the shared native search card and forwards Agent mode', async () => {
    const store = useWorkspaceStore()
    const open = vi.spyOn(store, 'openAgentSearchResult').mockResolvedValue(undefined)
    const results = (['files', 'library', 'components', 'literature'] as SearchSource[]).map(result)
    const wrapper = mount(AgentSearchResultBlocks, {
      props: { results, compact: false },
      global: {
        stubs: {
          SearchNativeResultCard: {
            props: ['result'],
            emits: ['activate'],
            template: '<button class="native-result" @click="$emit(\'activate\', result)">{{ result.source }}</button>',
          },
        },
      },
    })

    expect(wrapper.findAll('.native-result')).toHaveLength(4)
    await wrapper.findAll('.native-result')[1]?.trigger('click')
    expect(open).toHaveBeenLastCalledWith(results[1], false)

    await wrapper.setProps({ compact: true })
    await wrapper.findAll('.native-result')[2]?.trigger('click')
    expect(open).toHaveBeenLastCalledWith(results[2], true)
  })
})
