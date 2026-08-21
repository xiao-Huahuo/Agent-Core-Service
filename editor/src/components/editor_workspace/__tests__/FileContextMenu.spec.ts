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

  it('keeps ingestion and graph extraction adjacent with status-aware labels', () => {
    const wrapper = mountMenu({
      name: 'notes.md',
      path: 'notes.md',
      isDir: false,
      indexStatus: 'indexed',
      graphStatus: 'graphed',
    })
    const labels = wrapper.findAll('.context-menu > button').map((button) => button.text().replace(/\s/g, ''))

    expect(labels).not.toContain('在图谱中显示Ctrl+G')
    expect(labels).toContain('重新灌库文件')
    expect(labels).toContain('重新抽取图谱')
    expect(labels.indexOf('重新抽取图谱')).toBe(labels.indexOf('重新灌库文件') + 1)
  })

  it('uses first-run labels for dirty files', () => {
    const wrapper = mountMenu({
      name: 'draft.md',
      path: 'draft.md',
      isDir: false,
      indexStatus: 'dirty',
      graphStatus: 'dirty',
    })

    expect(wrapper.text()).toContain('灌库文件')
    expect(wrapper.text()).toContain('抽取图谱')
    expect(wrapper.text()).not.toContain('重新灌库文件')
    expect(wrapper.text()).not.toContain('重新抽取图谱')
  })

  it('keeps ingestion controls disabled for dot directories without blocking dot files', () => {
    const dotDirectoryMenu = mountMenu({
      name: '.git',
      path: '.git',
      isDir: true,
      indexStatus: 'ignored',
      graphStatus: 'ignored',
    })
    const dotFileMenu = mountMenu({
      name: '.notes.md',
      path: '.notes.md',
      isDir: false,
      indexStatus: 'dirty',
      graphStatus: 'dirty',
    })

    expect(buttonByText(dotDirectoryMenu, '灌库文件夹').attributes('disabled')).toBeDefined()
    expect(buttonByText(dotDirectoryMenu, '文件夹抽取图谱').attributes('disabled')).toBeDefined()
    expect(buttonByText(dotDirectoryMenu, '取消屏蔽文件夹').attributes('disabled')).toBeDefined()
    expect(buttonByText(dotFileMenu, '灌库文件').attributes('disabled')).toBeUndefined()
  })

  it('places privacy directly below favorite and emits its dedicated action', async () => {
    const wrapper = mountMenu({ name: 'private.md', path: 'private.md', isDir: false })
    const labels = wrapper.findAll('.context-menu > button').map((button) => button.text().replace(/\s/g, ''))

    expect(labels.indexOf('隐私化')).toBe(labels.indexOf('收藏') + 1)
    await buttonByText(wrapper, '隐私化').trigger('click')
    expect(wrapper.emitted('togglePrivacy')).toHaveLength(1)
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
      '灌库文件',
      '抽取图谱',
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
