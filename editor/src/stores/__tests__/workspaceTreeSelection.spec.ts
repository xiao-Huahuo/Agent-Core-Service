/*
 * Workspace file tree selection tests.
 *
 * Usage:
 * Verifies keyboard-modified file tree selection behavior owned by the
 * workspace store, without rendering the full file tree component.
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
  readKnowledgeFile: vi.fn(),
  rebuildKnowledgeGraph: vi.fn(),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  searchKnowledge: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn(),
}))

describe('workspace file tree selection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('keeps the current single selection when additive selection starts', () => {
    const workspaceStore = useWorkspaceStore()
    const firstNode = { name: 'a.md', path: 'docs/a.md', isDir: false }
    const secondNode = { name: 'b.md', path: 'docs/b.md', isDir: false }

    workspaceStore.selectTreeNode(firstNode)
    workspaceStore.selectTreeNode(secondNode, { additive: true })

    expect([...workspaceStore.selectedTreePaths].sort()).toEqual(['docs/a.md', 'docs/b.md'])
    expect(workspaceStore.selectedTreePath).toBe('docs/b.md')
    expect(workspaceStore.treeSelectionCleared).toBe(false)
  })

  it('removes an already selected node when additive selection clicks it again', () => {
    const workspaceStore = useWorkspaceStore()
    const firstNode = { name: 'a.md', path: 'docs/a.md', isDir: false }
    const secondNode = { name: 'b.md', path: 'docs/b.md', isDir: false }

    workspaceStore.selectTreeNode(firstNode)
    workspaceStore.selectTreeNode(secondNode, { additive: true })
    workspaceStore.selectTreeNode(secondNode, { additive: true })

    expect([...workspaceStore.selectedTreePaths]).toEqual(['docs/a.md'])
    expect(workspaceStore.selectedTreePath).toBe('docs/a.md')
    expect(workspaceStore.treeSelectionCleared).toBe(false)
  })

  it('clears tree focus when additive selection removes the last selected node', () => {
    const workspaceStore = useWorkspaceStore()
    const node = { name: 'a.md', path: 'docs/a.md', isDir: false }

    workspaceStore.selectTreeNode(node)
    workspaceStore.selectTreeNode(node, { additive: true })

    expect([...workspaceStore.selectedTreePaths]).toEqual([])
    expect(workspaceStore.selectedTreePath).toBe('')
    expect(workspaceStore.treeSelectionCleared).toBe(true)
  })
})
