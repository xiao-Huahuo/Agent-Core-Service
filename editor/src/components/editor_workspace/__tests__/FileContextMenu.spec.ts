/*
 * Knowledge file context-menu visualization tests.
 *
 * Verifies that HTML visualization is available for files and remains
 * unavailable for directories.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import FileContextMenu from '../FileContextMenu.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'

const menuStyle = { left: '0px', top: '0px' }

function mountMenu(node: KnowledgeFileNode) {
  return mount(FileContextMenu, {
    props: {
      node,
      canPaste: false,
      menuStyle,
    },
  })
}

describe('FileContextMenu HTML visualization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('emits htmlVisualize for a file', async () => {
    const wrapper = mountMenu({ name: 'notes.md', path: 'notes.md', isDir: false })

    await wrapper.get('[data-action="html-visualize"]').trigger('click')

    expect(wrapper.emitted('htmlVisualize')).toHaveLength(1)
  })

  it('disables HTML visualization for a directory', async () => {
    const wrapper = mountMenu({ name: 'docs', path: 'docs', isDir: true })
    const action = wrapper.get('[data-action="html-visualize"]')

    expect(action.attributes('disabled')).toBeDefined()
    await action.trigger('click')
    expect(wrapper.emitted('htmlVisualize')).toBeUndefined()
  })
})
