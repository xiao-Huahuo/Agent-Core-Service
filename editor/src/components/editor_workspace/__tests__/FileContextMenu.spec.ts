/*
 * Knowledge file context-menu visualization tests.
 *
 * Verifies that HTML visualization is available for files and remains
 * unavailable for directories.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import FileContextMenu from '../FileContextMenu.vue'
import contextMenuSource from '../FileContextMenu.vue?raw'
import type { KnowledgeFileNode } from '@/types/knowledge'

const menuStyle = { left: '0px', top: '0px' }

function mountMenu(node: KnowledgeFileNode, props: { canPaste?: boolean; selectionCount?: number } = {}) {
  return mount(FileContextMenu, {
    props: {
      node,
      canPaste: props.canPaste ?? false,
      menuStyle,
      selectionCount: props.selectionCount ?? 0,
    },
  })
}

function buttonByText(wrapper: VueWrapper, label: string) {
  const compactLabel = label.replace(/\s/g, '')
  const button = wrapper
    .findAll('button')
    .find((item) => item.text().replace(/\s/g, '') === compactLabel)
  if (!button) {
    throw new Error(`Button not found: ${label}`)
  }
  return button
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

  it('keeps only batch-safe actions enabled for multi-selection', () => {
    const wrapper = mountMenu(
      { name: 'notes.md', path: 'notes.md', isDir: false },
      { canPaste: true, selectionCount: 3 },
    )
    const enabledLabels = [
      '复制Ctrl+C',
      '剪切Ctrl+X',
      '粘贴Ctrl+V',
      '在文件夹中显示',
      '文件抽取图谱',
      '灌库文件',
      '屏蔽文件',
      '删除Ctrl+D',
    ]
    const disabledLabels = [
      '新建',
      '新建文件Ctrl+N',
      '新建文件夹Ctrl+Shift+N',
      '复制信息',
      '复制名称',
      '复制绝对路径',
      '复制相对路径',
      '重命名Ctrl+M',
      '用默认程序打开',
      '在图谱中显示Ctrl+G',
      'HTML可视化',
    ]

    for (const label of enabledLabels) {
      expect(buttonByText(wrapper, label).attributes('disabled')).toBeUndefined()
    }
    for (const label of disabledLabels) {
      expect(buttonByText(wrapper, label).attributes('disabled')).toBeDefined()
    }
  })

  it('uses dropdown entrance motion for the menu and submenus', () => {
    expect(contextMenuSource).toContain('animation: context-menu-in 160ms')
    expect(contextMenuSource).toContain('animation: context-submenu-in 150ms')
    expect(contextMenuSource).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
