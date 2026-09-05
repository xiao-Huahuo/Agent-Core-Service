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

const apiMocks = vi.hoisted(() => ({
  readKnowledgeFile: vi.fn(),
  fetchKnowledgeGraph: vi.fn(),
  deleteKnowledgeGraphNode: vi.fn(),
  clearKnowledgeGraphDocument: vi.fn(),
}))

vi.mock('@/api/knowledge', () => ({
  readKnowledgeFile: apiMocks.readKnowledgeFile,
  fetchKnowledgeGraph: apiMocks.fetchKnowledgeGraph,
  deleteKnowledgeGraphNode: apiMocks.deleteKnowledgeGraphNode,
  clearKnowledgeGraphDocument: apiMocks.clearKnowledgeGraphDocument,
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
  emits: ['node-select', 'node-open', 'node-context'],
  template: `
    <div>
      <button class="canvas-node" @click="$emit('node-select', model.nodes[0])">node</button>
      <button
        v-for="node in model.nodes"
        :key="node.id"
        :class="['context-node', node.kind]"
        @contextmenu.prevent.stop="$emit('node-context', { node, clientX: 48, clientY: 64 })"
      >{{ node.label }}</button>
    </div>
  `,
})

describe('GraphPane wiki-link mode', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    })
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
    apiMocks.fetchKnowledgeGraph.mockReset()
    apiMocks.fetchKnowledgeGraph.mockResolvedValue({
      nodes: [
        { id: 'doc-1', label: 'source.md', kind: 'document', metadata: { relative_path: 'source.md' } },
        { id: 'entity-1', label: 'MetaWeave', kind: 'entity' },
      ],
      links: [{ id: 'mention-1', source: 'doc-1', target: 'entity-1', kind: 'mentions' }],
      stats: {},
    })
    apiMocks.deleteKnowledgeGraphNode.mockReset()
    apiMocks.deleteKnowledgeGraphNode.mockResolvedValue({ ok: true, deleted_nodes: 1, deleted_edges: 1 })
    apiMocks.clearKnowledgeGraphDocument.mockReset()
    apiMocks.clearKnowledgeGraphDocument.mockResolvedValue({ ok: true, deleted_nodes: 1, deleted_edges: 1 })
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

  it('provides the ordered entity actions and deletes the node through the API', async () => {
    const wrapper = mount(GraphPane, {
      attachTo: document.body,
      global: { stubs: { KnowledgeGraphCanvas: CanvasStub, IcIcon: true } },
    })
    await flushPromises()

    await wrapper.get('.context-node.entity').trigger('contextmenu')
    await flushPromises()
    expect(wrapper.findAll('.graph-node-context-menu button').map((button) => button.text())).toEqual([
      '详情', '复制名称', '删除',
    ])

    await wrapper.findAll('.graph-node-context-menu button')[0]!.trigger('click')
    expect(wrapper.get('.graph-sidebar').classes()).toContain('open')
    expect(wrapper.get('.selected-node-name').text()).toContain('MetaWeave')

    await wrapper.get('.context-node.entity').trigger('contextmenu')
    await wrapper.findAll('.graph-node-context-menu button')[2]!.trigger('click')
    await flushPromises()
    expect(apiMocks.deleteKnowledgeGraphNode).toHaveBeenCalledWith('graph-user', 'entity-1')
    wrapper.unmount()
  })

  it('provides document details, sidebar open, copy, and clear actions in order', async () => {
    const wrapper = mount(GraphPane, {
      attachTo: document.body,
      global: { stubs: { KnowledgeGraphCanvas: CanvasStub, IcIcon: true } },
    })
    const workspaceStore = useWorkspaceStore()
    const openEditorSidebar = vi.spyOn(workspaceStore, 'openEditorSidebar').mockResolvedValue(undefined)
    await flushPromises()

    await wrapper.get('.context-node.document').trigger('contextmenu')
    await flushPromises()
    expect(wrapper.findAll('.graph-node-context-menu button').map((button) => button.text())).toEqual([
      '详情', '打开', '复制名称', '清空节点',
    ])

    await wrapper.findAll('.graph-node-context-menu button')[1]!.trigger('click')
    await flushPromises()
    expect(openEditorSidebar).toHaveBeenCalledWith(expect.objectContaining({ path: 'source.md', isDir: false }))

    await wrapper.get('.context-node.document').trigger('contextmenu')
    await wrapper.findAll('.graph-node-context-menu button')[3]!.trigger('click')
    await flushPromises()
    expect(apiMocks.clearKnowledgeGraphDocument).toHaveBeenCalledWith('graph-user', 'doc-1')
    wrapper.unmount()
  })
})
