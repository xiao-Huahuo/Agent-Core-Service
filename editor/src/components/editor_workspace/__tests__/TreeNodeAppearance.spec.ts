/**
 * File-tree selection appearance regression.
 *
 * Usage:
 * Keeps file and folder rows aligned with the component-library sidebar's
 * soft primary selection surface and animated leading indicator.
 */
import { describe, expect, it } from 'vitest'

import treeNodeSource from '@/components/editor_workspace/TreeNode.vue?raw'

describe('TreeNode appearance', () => {
  it('uses the component-sidebar active selection effect', () => {
    expect(treeNodeSource).toMatch(/\.tree-label,[\s\S]*\.file-item \{[^}]*position: relative;[^}]*overflow: hidden;/)
    expect(treeNodeSource).toMatch(/\.tree-label::before,[\s\S]*\.file-item::before \{[^}]*width: 3px;[^}]*transform: scaleY\(0\);/)
    expect(treeNodeSource).toMatch(/\.is-selected \{[^}]*background-color: var\(--color-primary-soft\);[^}]*color: var\(--color-primary\);/)
    expect(treeNodeSource).toMatch(/\.is-selected::before \{[^}]*transform: scaleY\(1\);/)
  })
})
