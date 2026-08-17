/*
 * Workspace graph pane mode tests.
 *
 * Usage:
 * Verifies the fourth graph mode loads real Markdown sources, exposes link
 * counts, and turns a canvas node selection into an immediate file-open event.
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GraphPane from '../GraphPane.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

const apiMocks = vi.hoisted(() => ({ readKnowledgeFile: vi.fn() }))

vi.mock('@/api/knowledge', () => ({
  readKnowledgeFile: apiMocks.readKnowledgeFile,
  fetchKnowledgeGraph: vi.fn().mockResolvedValue({ nodes: [], links: [] }),
  deduplicateKnowledgeGraph: vi.fn(),
  getDedupStatus: vi.fn(),
}))

vi.mock('@/api/library', () => ({
  listLibraryItems: vi.fn().mockResolvedValue({ items: [] }),
  listLibraryTags: vi.fn().mockResolvedValue({ tags: [] }),
}))

const CanvasStub = defineComponent({
  name: 'KnowledgeGraphCanvas',
  props: ['model'],
  emits: ['node-select', 'node-open'],
  template: '<button class="canvas-node" @click="$emit(\'node-select\', model.nodes[0])">node</button>',
})

describe('GraphPane wiki-link mode', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.readKnowledgeFile.mockReset()
    apiMocks.readKnowledgeFile.mockImplementation(async (_userId: string, path: string) => ({
      path,
      content: path.endsWith('source.md') ? '[[target]] ![[target#摘要]]' : '# 目标',
    }))
    const settingsStore = useSettingsStore()
    settingsStore.profile.userId = 'graph-user'
    const workspaceStore = useWorkspaceStore()
    workspaceStore.tree = [
      { name: 'source.md', path: 'source.md', isDir: false },
      { name: 'target.md', path: 'target.md', isDir: false },
    ]
  })

  it('loads all Markdown files, reports both link kinds, and opens on one click', async () => {
    const wrapper = mount(GraphPane, {
      global: { stubs: { KnowledgeGraphCanvas: CanvasStub, IcIcon: true } },
    })

    await wrapper.get('.graph-mode-button:nth-of-type(4)').trigger('click')
    await flushPromises()

    expect(apiMocks.readKnowledgeFile).toHaveBeenCalledTimes(2)
    expect(wrapper.get('.graph-stat').text()).toContain('2 文档 / 1 反向 / 1 嵌入')
    await wrapper.get('.canvas-node').trigger('click')
    expect(wrapper.emitted('open-node')?.[0]?.[0]).toMatchObject({ path: 'source.md', kind: 'document' })
  })
})
