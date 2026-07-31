/*
 * Git status presentation structure tests.
 *
 * Usage:
 * Verifies that file tree and resource manager names share the Git store's
 * semantic path color helper, including directories with changed descendants.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const workspaceRoot = resolve(__dirname, '..')
const treeNodeSource = readFileSync(resolve(workspaceRoot, 'TreeNode.vue'), 'utf-8')
const treePanelSource = readFileSync(resolve(workspaceRoot, 'FileTreePanel.vue'), 'utf-8')
const resourceManagerSource = readFileSync(resolve(workspaceRoot, 'FileResourceManager.vue'), 'utf-8')
const gitStoreSource = readFileSync(resolve(__dirname, '..', '..', '..', 'stores', 'git.ts'), 'utf-8')

describe('Git status presentation', () => {
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
})
