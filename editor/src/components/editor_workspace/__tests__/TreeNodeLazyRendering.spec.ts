/**
 * File-tree lazy rendering regression.
 *
 * Usage:
 * Verifies that collapsed folders do not mount descendant TreeNode components
 * and that expanding the folder mounts its direct subtree.
 */
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import TreeNode from '@/components/editor_workspace/TreeNode.vue'

describe('TreeNode lazy rendering', () => {
  it('mounts folder children only while the folder is expanded', async () => {
    const wrapper = mount(TreeNode, {
      props: {
        node: {
          name: 'folder',
          path: 'folder',
          isDir: true,
          children: [{ name: 'child.md', path: 'folder/child.md', isDir: false }],
        },
        depth: 0,
        expandedPaths: new Set<string>(),
        selectedPath: '',
        selectedPaths: new Set<string>(),
        dirtyPaths: new Set<string>(),
        editingPath: '',
        editingValue: '',
      },
      global: {
        plugins: [createPinia()],
        stubs: { IcIcon: true, FavoriteButton: true, PrivacyButton: true },
      },
    })

    expect(wrapper.findAll('.tree-item')).toHaveLength(1)

    await wrapper.setProps({ expandedPaths: new Set(['folder']) })

    expect(wrapper.findAll('.tree-item')).toHaveLength(2)
    expect(wrapper.text()).toContain('child.md')
  })
})
