/*
 * Workspace Markdown HTML visualization selection tests.
 *
 * Usage:
 * Verifies that document selection for the MD-HTML page remains separate from
 * the one-click Agent visualization workflow.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
})
