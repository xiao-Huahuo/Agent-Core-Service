/*
 * File-tree filename search tests.
 *
 * Usage:
 * Verifies the filename filter keeps the original tree shape (ancestors stay,
 * a matched directory keeps its subtree), that the expanded-path collector
 * covers every remaining directory, and that the panel dropdown filters live.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, h } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import FileTreePanel from '../FileTreePanel.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'
import { collectExpandedPathsForFilteredTree, filterTreeByQuery } from '../fileTreeSearch'

const storeState = vi.hoisted(() => ({
  tree: [
    { name: 'docs', path: 'docs', isDir: true, children: [
      { name: 'guide', path: 'docs/guide', isDir: true, children: [
        { name: 'setup.md', path: 'docs/guide/setup.md', isDir: false },
        { name: 'notes.md', path: 'docs/guide/notes.md', isDir: false },
      ] },
      { name: 'README.md', path: 'docs/README.md', isDir: false },
    ] },
    { name: 'notes', path: 'notes', isDir: true, children: [
      { name: 'meeting-2026.md', path: 'notes/meeting-2026.md', isDir: false },
    ] },
    { name: 'index.md', path: 'index.md', isDir: false },
  ],
}))

vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: () => ({
    tree: storeState.tree,
    flatNodes: [],
    expandedPaths: new Set(['docs']),
    selectedTreePaths: new Set(),
    selectedTreePath: '',
    selectedPath: '',
    treeLoading: false,
    dirtyFilePaths: new Set(),
    recentFileVisits: [],
    loadKnowledgeTree: vi.fn(() => Promise.resolve()),
    startFileWatcher: vi.fn(),
    stopFileWatcher: vi.fn(),
    selectTreeNode: vi.fn(),
    selectFile: vi.fn(),
    setMainView: vi.fn(),
    toggleDirectory: vi.fn(),
    showToast: vi.fn(),
  }),
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    showIndexColumn: false,
    showGraphColumn: false,
    isDark: false,
    profile: { knowledgeDir: '' },
  }),
}))

vi.mock('@/stores/git', () => ({
  useGitStore: () => ({ refresh: vi.fn() }),
}))

/** Stub that renders each rendered root node name so filtering can be asserted. */
const TreeNodeStub = defineComponent({
  name: 'TreeNode',
  props: ['node'],
  setup(props) {
    return () => h('span', { class: 'stub-node' }, props.node.name)
  },
})

function nodeNames(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.stub-node').map((item) => item.text())
}

function mountPanel() {
  return mount(FileTreePanel, {
    global: {
      stubs: {
        TreeNode: TreeNodeStub,
        RecentFileList: true,
        FileContextMenu: true,
      },
    },
  })
}

function node(name: string, children?: KnowledgeFileNode[]): KnowledgeFileNode {
  return {
    name,
    path: children ? name : `${name}.md`,
    isDir: Boolean(children),
    children,
  }
}

const tree: KnowledgeFileNode[] = [
  node('docs', [
    node('guide', [node('setup'), node('notes')]),
    node('README'),
  ]),
  node('notes', [node('meeting-2026')]),
  node('index.md'),
]

describe('filterTreeByQuery', () => {
  it('returns the original tree for an empty query', () => {
    expect(filterTreeByQuery(tree, '')).toBe(tree)
    expect(filterTreeByQuery(tree, '   ')).toBe(tree)
  })

  it('keeps matching files under their ancestor directories', () => {
    const result = filterTreeByQuery(tree, 'setup')
    expect(result.length).toBe(1)
    expect(result[0]?.name).toBe('docs')
    expect(result[0]?.children?.[0]?.name).toBe('guide')
    expect(result[0]?.children?.[0]?.children?.map((c) => c.name)).toEqual(['setup'])
  })

  it('keeps the whole subtree when a directory name matches', () => {
    // guide/notes.md 与根级 notes 目录同名,两条路径都命中。
    const result = filterTreeByQuery(tree, 'notes')
    expect(result.map((r) => r.name)).toEqual(['docs', 'notes'])
    const notesNode = result[1]!
    expect(notesNode.children?.map((c) => c.name)).toEqual(['meeting-2026'])
  })

  it('keeps ancestors when a nested directory name matches', () => {
    const result = filterTreeByQuery(tree, 'guide')
    expect(result.map((r) => r.name)).toEqual(['docs'])
    expect(result[0]?.children?.map((c) => c.name)).toEqual(['guide'])
    expect(result[0]?.children?.[0]?.children?.map((c) => c.name)).toEqual(['setup', 'notes'])
  })

  it('matches filenames case-insensitively', () => {
    const result = filterTreeByQuery(tree, 'SETUP')
    expect(result[0]?.children?.[0]?.children?.[0]?.name).toBe('setup')
  })

  it('drops unmatched subtrees and siblings', () => {
    const result = filterTreeByQuery(tree, 'index')
    expect(result.map((r) => r.name)).toEqual(['index.md'])
  })
})

describe('collectExpandedPathsForFilteredTree', () => {
  it('collects every directory path in the filtered result', () => {
    const filtered = filterTreeByQuery(tree, 'guide')
    const paths = collectExpandedPathsForFilteredTree(filtered)
    expect(paths.has('docs')).toBe(true)
    expect(paths.has('guide')).toBe(true)
    expect(paths.size).toBe(2)
  })
})

describe('FileTreePanel search wiring', () => {
  it('ships a search icon, dropdown input and uses the shared helpers', () => {
    const source = readFileSync(resolve(__dirname, '..', 'FileTreePanel.vue'), 'utf-8')
    expect(source).toContain('filterTreeByQuery')
    expect(source).toContain('collectExpandedPathsForFilteredTree')
    expect(source).toContain('treeSearchOpen')
    expect(source).toContain('placeholder="按文件名搜索"')
    expect(source).toContain('title="搜索文件"')
    expect(source).toContain(':expanded-paths="effectiveExpandedPaths"')
    expect(source).toContain('() => privacyStore.activeLibraryId()')
    expect(source).toContain("privacyStore.load(userId, 'knowledge_path', libraryId)")
  })
})

describe('FileTreePanel search interaction', () => {
  it('filters the tree by filename and restores it after clearing', async () => {
    const wrapper = mountPanel()
    expect(nodeNames(wrapper)).toEqual(['docs', 'notes', 'index.md'])

    await wrapper.get('[aria-label="搜索文件"]').trigger('click')
    const input = wrapper.get('.tree-search input')
    expect((input.element as HTMLInputElement).value).toBe('')

    await input.setValue('guide')
    expect(nodeNames(wrapper)).toEqual(['docs'])

    await wrapper.get('[aria-label="清除搜索"]').trigger('click')
    expect(nodeNames(wrapper)).toEqual(['docs', 'notes', 'index.md'])
  })

  it('closes the dropdown with Escape', async () => {
    const wrapper = mountPanel()
    await wrapper.get('[aria-label="搜索文件"]').trigger('click')
    expect(wrapper.find('.tree-search').exists()).toBe(true)

    await wrapper.get('.tree-search input').trigger('keydown.esc')
    expect(wrapper.find('.tree-search').exists()).toBe(false)
    expect(nodeNames(wrapper)).toEqual(['docs', 'notes', 'index.md'])
  })
})
