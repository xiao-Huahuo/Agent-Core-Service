/*
 * Recent file list interaction tests.
 *
 * Usage:
 * Verifies that recent cards expose the shared context-menu trigger while
 * keeping index and graph states as accessible icon-only indicators.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RecentFileList from '../RecentFileList.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'
import type { RecentFileGroup } from '@/utils/recentFileHistory'

const node: KnowledgeFileNode = {
  name: 'notes.md',
  path: 'docs/notes.md',
  isDir: false,
  indexStatus: 'indexed',
  graphStatus: 'graphed',
}

const groups: RecentFileGroup[] = [{
  key: 'today',
  label: '今天',
  items: [{ node, lastViewedAt: '2026-07-30T09:00:00+08:00' }],
}]

function mountList() {
  return mount(RecentFileList, {
    props: {
      groups,
      selectedPath: '',
      hasHistory: true,
    },
    global: {
      stubs: {
        RecentFileThumbnail: true,
      },
    },
  })
}

describe('RecentFileList interactions', () => {
  it('emits the selected file and pointer event on right click', async () => {
    const wrapper = mountList()

    await wrapper.get('.recent-file-card').trigger('contextmenu')

    expect(wrapper.emitted('contextMenu')?.[0]?.[0]).toEqual(node)
    expect(wrapper.emitted('contextMenu')?.[0]?.[1]).toBeInstanceOf(MouseEvent)
  })

  it('renders status indicators as icons with accessible labels only', () => {
    const wrapper = mountList()

    expect(wrapper.find('[aria-label="已索引"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="已入图"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('已索引')
    expect(wrapper.text()).not.toContain('已入图')
  })
})
