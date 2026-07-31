/*
 * Git status presentation structure tests.
 *
 * Usage:
 * Verifies that file tree and resource manager names share the Git store's
 * semantic path color helper, including directories with changed descendants.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useGitStore } from '@/stores/git'

const workspaceRoot = resolve(__dirname, '..')
const treeNodeSource = readFileSync(resolve(workspaceRoot, 'TreeNode.vue'), 'utf-8')
const treePanelSource = readFileSync(resolve(workspaceRoot, 'FileTreePanel.vue'), 'utf-8')
const treePanelCssSource = readFileSync(resolve(workspaceRoot, 'FileTreePanel.css'), 'utf-8')
const resourceManagerSource = readFileSync(resolve(workspaceRoot, 'FileResourceManager.vue'), 'utf-8')
const resourceManagerCssSource = readFileSync(resolve(workspaceRoot, 'FileResourceManager.css'), 'utf-8')
const gitStoreSource = readFileSync(resolve(__dirname, '..', '..', '..', 'stores', 'git.ts'), 'utf-8')
const workspaceStoreSource = readFileSync(resolve(__dirname, '..', '..', '..', 'stores', 'workspace.ts'), 'utf-8')
const editorWorkspaceSource = readFileSync(resolve(__dirname, '..', '..', '..', 'views', 'EditorWorkspace.vue'), 'utf-8')

describe('Git status presentation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses one Git path helper for file and directory name colors', () => {
    expect(gitStoreSource).toContain('function statusClassForPath')
    expect(gitStoreSource).toContain('DIRECTORY_STATE_PRIORITY')
    expect(treeNodeSource).toContain('gitStore.statusClassForPath(props.node.path, props.node.isDir)')
    expect(resourceManagerSource).toContain('gitStore.statusClassForPath(node.path, node.isDir)')
  })

  it('refreshes Git status when Git-colored file surfaces mount', () => {
    expect(treePanelSource).toContain('void gitStore.refresh()')
    expect(resourceManagerSource).toContain('void gitStore.refresh()')
  })

  it('refreshes Git status after saving a knowledge file', () => {
    expect(workspaceStoreSource).toContain("window.dispatchEvent(new CustomEvent('metaweave-knowledge-file-change'))")
    expect(editorWorkspaceSource).toContain(
      "window.addEventListener('metaweave-knowledge-file-change', refreshGitAfterKnowledgeFileChange)",
    )
    expect(editorWorkspaceSource).toContain('void gitStore.refresh()')
    expect(gitStoreSource).toContain('const refreshQueued = ref(false)')
    expect(gitStoreSource).toContain('refreshQueued.value = true')
  })

  it('matches Git paths with an extra root segment for files and directories', () => {
    const gitStore = useGitStore()
    gitStore.status = {
      initialized: true,
      repository_root: 'D:/knowledge',
      current_branch: 'main',
      upstream: '',
      ahead: 0,
      behind: 0,
      detached: false,
      branches: [],
      remote_branches: [],
      remotes: [],
      changes: [{
        path: 'knowledge/docs/a.md',
        name: 'a.md',
        directory: 'knowledge/docs',
        old_path: '',
        code: ' M',
        state: 'modified',
        staged: false,
        working_tree: true,
      }],
      untracked: [],
      has_changes: true,
    }

    expect(gitStore.statusClassForPath('docs/a.md', false)).toBe('git-modified')
    expect(gitStore.statusClassForPath('docs', true)).toBe('git-modified')
  })

  it('applies Git classes to rows and keeps the file tree scroll container bounded', () => {
    expect(treeNodeSource).toContain(':class="[')
    expect(resourceManagerSource).toContain('gitStatusClass(node),')
    expect(resourceManagerCssSource).toContain('.resource-row.git-modified .file-name')
    expect(treePanelCssSource).toMatch(/\.file-panel\s*\{[^}]*height:\s*100%/s)
    expect(treePanelCssSource).toMatch(/\.tree-root\s*\{[^}]*flex:\s*1 1 0/s)
  })
})
