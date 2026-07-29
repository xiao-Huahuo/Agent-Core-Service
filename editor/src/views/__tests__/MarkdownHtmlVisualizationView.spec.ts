/*
 * MD-HTML visualization page tests.
 *
 * Usage:
 * Verifies the page-facing name and explicit file-picker entry point without
 * starting the Agent visualization workflow.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import MarkdownHtmlVisualizationView from '@/views/MarkdownHtmlVisualizationView.vue'

vi.mock('@/api/agent', () => ({
  updateCurrentDocumentContext: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/settings', () => ({
  rebuildKnowledgeRootStream: vi.fn(),
}))

vi.mock('@/api/knowledge', () => ({
  buildKnowledgeEventsUrl: vi.fn(() => '/events'),
  copyKnowledgePath: vi.fn(),
  createKnowledgeFile: vi.fn(),
  createKnowledgeFolder: vi.fn(),
  deleteKnowledgePath: vi.fn(),
  deleteKnowledgeTrashEntry: vi.fn(),
  getKnowledgeGraphStatus: vi.fn(),
  ingestKnowledgeFileStream: vi.fn(),
  ingestKnowledgePathStream: vi.fn(),
  listKnowledgeFiles: vi.fn(),
  listKnowledgeTrash: vi.fn(),
  previewKnowledgeFile: vi.fn(),
  readKnowledgeFile: vi.fn(),
  rebuildKnowledgeGraph: vi.fn(),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  searchKnowledge: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn(),
}))

describe('MarkdownHtmlVisualizationView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('uses the MD-HTML page name and exposes file picker plus advanced options actions', async () => {
    const wrapper = mount(MarkdownHtmlVisualizationView, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    expect(wrapper.get('h1').text()).toBe('MD-HTML')
    expect(wrapper.text()).toContain('选择文件')
    expect(wrapper.text()).toContain('高级选项')
    expect(wrapper.text()).not.toContain('原结构模式')

    await wrapper.get('button[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.text()).toContain('原结构模式')
    expect(wrapper.text()).toContain('AI提炼模式')
    expect(wrapper.text()).toContain('强动效')
  })
})
