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
const gitApiSource = readFileSync(resolve(__dirname, '..', '..', '..', 'api', 'git.ts'), 'utf-8')
const uiSystemCssSource = readFileSync(resolve(__dirname, '..', '..', '..', 'assets', 'ui-system.css'), 'utf-8')
const workspaceStoreSource = readFileSync(resolve(__dirname, '..', '..', '..', 'stores', 'workspace.ts'), 'utf-8')
const editorWorkspaceSource = readFileSync(resolve(__dirname, '..', '..', '..', 'views', 'EditorWorkspace.vue'), 'utf-8')
const gitSidebarSource = readFileSync(resolve(workspaceRoot, '..', 'git_sidebar', 'GitSidebar.vue'), 'utf-8')

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
      ignored: [],
      has_changes: true,
    }

    expect(gitStore.statusClassForPath('docs/a.md', false)).toBe('git-modified')
    expect(gitStore.statusClassForPath('docs', true)).toBe('git-modified')
  })

  it('colors ignored files and directories with git-ignored while keeping change states', () => {
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
        path: 'docs/a.md',
        name: 'a.md',
        directory: 'docs',
        old_path: '',
        code: ' M',
        state: 'modified',
        staged: false,
        working_tree: true,
      }],
      untracked: [],
      ignored: [
        {
          path: 'scratch.log',
          name: 'scratch.log',
          directory: '',
          old_path: '',
          code: '!!',
          state: 'ignored',
          staged: false,
          working_tree: false,
        },
        {
          path: 'build/',
          name: 'build',
          directory: '',
          old_path: '',
          code: '!!',
          state: 'ignored',
          staged: false,
          working_tree: false,
        },
      ],
      has_changes: true,
    }

    // 直接被 .gitignore 命中的文件与整体忽略的目录都显示暗棕黄色。
    expect(gitStore.statusClassForPath('scratch.log', false)).toBe('git-ignored')
    expect(gitStore.statusClassForPath('build', true)).toBe('git-ignored')
    // Git 把整目录折叠为 `!! build/`,其下的具体文件也要推断为忽略色。
    expect(gitStore.statusClassForPath('build/out.log', false)).toBe('git-ignored')
    // 修改状态优先级高于忽略,目录含修改后代时仍显示修改色。
    expect(gitStore.statusClassForPath('docs', true)).toBe('git-modified')
  })

  it('applies Git classes to rows and keeps the file tree scroll container bounded', () => {
    expect(treeNodeSource).toContain(':class="[')
    expect(resourceManagerSource).toContain('gitStatusClass(node),')
    expect(resourceManagerCssSource).toContain('.resource-row.git-modified .file-name')
    expect(treePanelCssSource).toMatch(/\.file-panel\s*\{[^}]*height:\s*100%/s)
    expect(treePanelCssSource).toMatch(/\.tree-root\s*\{[^}]*flex:\s*1 1 0/s)
  })

  it('exposes ignored files only for coloring, never for sidebar selection', () => {
    // 后端通过独立 ignored 数组返回忽略文件;侧栏只渲染 changes/untracked。
    expect(gitApiSource).toContain("| 'ignored'")
    expect(gitApiSource).toContain('ignored: GitFileChange[]')
    expect(gitSidebarSource).toContain('gitStore.status.changes')
    expect(gitSidebarSource).toContain('gitStore.status.untracked')
    expect(gitSidebarSource).not.toContain('gitStore.status.ignored')

    // store 把 ignored 并入扁平列表驱动着色,并纳入目录优先级与空状态。
    expect(gitStoreSource).toContain('...status.value.ignored')
    expect(gitStoreSource).toContain("'ignored'")
    expect(gitStoreSource).toContain('ignored: [],')

    // 暗棕黄配色变量与两种视图的 git-ignored 规则。
    expect(uiSystemCssSource).toContain('--color-git-ignored: #a1842b')
    expect(treeNodeSource).toContain('.tree-row.git-ignored .node-name')
    expect(treeNodeSource).toContain('.node-name.git-ignored')
    expect(resourceManagerCssSource).toContain('.resource-row.git-ignored .file-name')
  })
})
