/*
 * Workspace Markdown HTML visualization selection tests.
 *
 * Usage:
 * Verifies that document selection for the MD-HTML page remains separate from
 * the one-click Agent visualization workflow.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ingestKnowledgeFileStream, listKnowledgeFiles } from '@/api/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

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
  readKnowledgeFile: vi.fn().mockResolvedValue({ content: '# Notes', mtime: '2026-07-29 10:00' }),
  rebuildKnowledgeGraph: vi.fn(),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  searchKnowledge: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn(),
}))

describe('workspace MD-HTML document selection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('selects a file and opens the MD-HTML page without starting the Agent workflow', async () => {
    const workspaceStore = useWorkspaceStore()
    const fileNode = { name: 'notes.md', path: 'docs/notes.md', isDir: false }
    workspaceStore.tree = [{ name: 'docs', path: 'docs', isDir: true, children: [fileNode] }]
    workspaceStore.pendingAgentPrompt = ''
    workspaceStore.agentSidebarOpen = true

    const ingestSpy = vi.spyOn(workspaceStore, 'ingestFile')

    await workspaceStore.selectMarkdownHtmlVisualizationDocument(fileNode)

    expect(workspaceStore.selectedPath).toBe('docs/notes.md')
    expect(workspaceStore.selectedTreePath).toBe('docs/notes.md')
    expect(workspaceStore.mainView).toBe('visualization')
    expect(workspaceStore.agentSidebarOpen).toBe(false)
    expect(workspaceStore.pendingAgentPrompt).toBe('')
    expect(ingestSpy).not.toHaveBeenCalled()
  })

  it('clears mounted HTML when switching the MD-HTML selected document', async () => {
    const workspaceStore = useWorkspaceStore()
    const firstNode = { name: 'first.md', path: 'docs/first.md', isDir: false }
    const secondNode = { name: 'second.md', path: 'docs/second.md', isDir: false }
    workspaceStore.tree = [{ name: 'docs', path: 'docs', isDir: true, children: [firstNode, secondNode] }]
    workspaceStore.showMarkdownHtmlVisualization({
      title: 'first',
      filename: 'first.html',
      path: 'runtime/visualizations/first.html',
      url: '/visualizations/first.html',
      source_path: 'docs/first.md',
      created_at: '2026-07-29T10:00:00',
    })

    await workspaceStore.selectMarkdownHtmlVisualizationDocument(secondNode)

    expect(workspaceStore.selectedPath).toBe('docs/second.md')
    expect(workspaceStore.markdownHtmlVisualizationOpen).toBe(false)
    expect(workspaceStore.markdownHtmlVisualization).toBeNull()
  })

  it('adds the custom requirement to the Agent visualization prompt', async () => {
    const settingsStore = useSettingsStore()
    const workspaceStore = useWorkspaceStore()
    const fileNode = { name: 'notes.md', path: 'docs/notes.md', isDir: false }
    settingsStore.profile.userId = 'user_1'
    workspaceStore.tree = [{ name: 'docs', path: 'docs', isDir: true, children: [fileNode] }]
    workspaceStore.setMarkdownHtmlVisualizationPreset('dashboard')
    workspaceStore.setMarkdownHtmlVisualizationOption('denseLayout', true)
    workspaceStore.setMarkdownHtmlVisualizationCustomRequirement('突出结论, 降低装饰密度')
    vi.mocked(ingestKnowledgeFileStream).mockResolvedValue({
      files_seen: 1,
      files_ingested: 1,
      chunks_created: 2,
    })
    vi.mocked(listKnowledgeFiles).mockResolvedValue({
      tree: [{ name: 'docs', path: 'docs', isDir: true, children: [fileNode] }],
    })

    await workspaceStore.startMarkdownHtmlVisualization(fileNode)

    expect(workspaceStore.pendingAgentPrompt).toContain('自定义要求:')
    expect(workspaceStore.pendingAgentPrompt).toContain('突出结论, 降低装饰密度')
    expect(workspaceStore.pendingAgentPrompt).toContain('展示预设')
    expect(workspaceStore.pendingAgentPrompt).toContain('仪表盘导向')
    expect(workspaceStore.pendingAgentPrompt).toContain('高信息密度: 启用')
  })
})
