/*
 * Obsidian-style wiki-link utility regression tests.
 *
 * Usage:
 * Keeps editor suggestions, preview navigation, heading embeds, and recursion
 * limits on one shared syntax contract.
 */

import { describe, expect, it } from 'vitest'

import {
  WIKI_EMBED_MAX_DEPTH,
  extractWikiSection,
  findWikiLinkTrigger,
  parseWikiLink,
  resolveWikiTargetPath,
  wikiLinkSuggestions,
} from '../wikiLinks'
import type { KnowledgeFileNode } from '@/types/knowledge'

const tree: KnowledgeFileNode[] = [
  {
    name: '机器学习',
    path: '机器学习',
    isDir: true,
    children: [
      { name: '深度学习.md', path: '机器学习/深度学习.md', isDir: false },
      { name: '模型图.png', path: '机器学习/static/模型图.png', isDir: false },
    ],
  },
  { name: 'tmp.md', path: '杂项/tmp.md', isDir: false },
]

describe('wikiLinks', () => {
  it('parses direct, aliased, heading, and embedded links', () => {
    expect(parseWikiLink('深度学习')).toEqual({ file: '深度学习', heading: '', blockId: '', alias: '' })
    expect(parseWikiLink('深度学习|别名')).toEqual({ file: '深度学习', heading: '', blockId: '', alias: '别名' })
    expect(parseWikiLink('深度学习#优化器|Adam')).toEqual({ file: '深度学习', heading: '优化器', blockId: '', alias: 'Adam' })
    expect(parseWikiLink('tmp^825bcf')).toEqual({ file: 'tmp', heading: '', blockId: '825bcf', alias: '' })
  })

  it('opens suggestions after [[ and ![[ and filters the typed filename', () => {
    expect(findWikiLinkTrigger('前文 [[', 5)).toMatchObject({ start: 3, embed: false, query: '' })
    expect(findWikiLinkTrigger('![[深度', 5)).toMatchObject({ start: 0, embed: true, query: '深度' })
    expect(findWikiLinkTrigger('[[深度]]', 6)).toBeNull()

    expect(wikiLinkSuggestions(tree, '深度').map((item) => item.path)).toEqual(['机器学习/深度学习.md'])
    expect(wikiLinkSuggestions(tree, '')).toHaveLength(3)
    expect(wikiLinkSuggestions(tree, '模型')[0]).toMatchObject({
      title: '模型图.png',
      folder: '机器学习/static/',
      target: '机器学习/static/模型图.png',
    })
  })

  it('resolves relative paths, extensionless names, and the current document', () => {
    expect(resolveWikiTargetPath('深度学习', tree, '机器学习/索引.md')).toBe('机器学习/深度学习.md')
    expect(resolveWikiTargetPath('机器学习/static/模型图.png', tree, '杂项/tmp.md')).toBe('机器学习/static/模型图.png')
    expect(resolveWikiTargetPath('', tree, '杂项/tmp.md')).toBe('杂项/tmp.md')
    expect(resolveWikiTargetPath('不存在', tree, '杂项/tmp.md')).toBe('')
  })

  it('extracts one heading section or one block without swallowing the next peer heading', () => {
    const markdown = '# 文档\n\n## 数学公式\n公式正文 ^math\n\n### 子标题\n子内容\n\n## 表格\n表格正文'
    expect(extractWikiSection(markdown, { heading: '数学公式', blockId: '' })).toBe(
      '## 数学公式\n公式正文 ^math\n\n### 子标题\n子内容',
    )
    expect(extractWikiSection(markdown, { heading: '', blockId: 'math' })).toBe('公式正文')
    expect(extractWikiSection(markdown, { heading: '不存在', blockId: '' })).toBe('')
  })

  it('caps recursive embeds at five levels', () => {
    expect(WIKI_EMBED_MAX_DEPTH).toBe(5)
  })
})
