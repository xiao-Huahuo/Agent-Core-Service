/*
 * Wiki-link preview DOM tests.
 *
 * Usage:
 * Verifies real DOM replacement, local image embedding, and the five-level
 * recursive embed boundary independently of Vditor's rendering lifecycle.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { KnowledgeFileNode } from '@/types/knowledge'
import { decorateWikiPreview } from '../wikiPreview'

const knowledgeMocks = vi.hoisted(() => ({ readKnowledgeFile: vi.fn() }))

vi.mock('@/api/knowledge', () => ({ readKnowledgeFile: knowledgeMocks.readKnowledgeFile }))

const tree: KnowledgeFileNode[] = [
  { name: 'target.md', path: 'notes/target.md', isDir: false },
  { name: 'loop.md', path: 'notes/loop.md', isDir: false },
  { name: 'chart.png', path: 'notes/static/chart.png', isDir: false },
]

function context() {
  return {
    tree,
    currentPath: 'notes/source.md',
    userId: 'user-1',
    cache: new Map<string, string>(),
  }
}

describe('wikiPreview', () => {
  beforeEach(() => knowledgeMocks.readKnowledgeFile.mockReset())

  it('turns normal wiki syntax into a resolved aliased navigation link', async () => {
    const root = document.createElement('div')
    root.innerHTML = '<p>前往 [[target#章节|阅读章节]]。</p><code>[[target]]</code>'

    await decorateWikiPreview(root, context())

    const link = root.querySelector<HTMLAnchorElement>('.wiki-link')
    expect(link?.textContent).toBe('阅读章节')
    expect(link?.dataset.wikiDestination).toBe('target#章节|阅读章节')
    expect(link?.dataset.wikiPath).toBe('notes/target.md')
    expect(root.querySelector('code')?.textContent).toBe('[[target]]')
  })

  it('embeds only the requested Markdown heading and renders nested markup', async () => {
    knowledgeMocks.readKnowledgeFile.mockResolvedValue({
      content: '# 标题\n\n## 章节\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\n## 后续\n不应嵌入',
    })
    const root = document.createElement('div')
    root.textContent = '![[target#章节]]'

    await decorateWikiPreview(root, context())

    expect(root.querySelector('.wiki-embed')).not.toBeNull()
    expect(root.querySelector('table')?.textContent).toContain('A')
    expect(root.textContent).not.toContain('不应嵌入')
  })

  it('renders adjacent inline formulas in embeds without treating their boundary as display math', async () => {
    knowledgeMocks.readKnowledgeFile.mockResolvedValue({
      content: String.raw`- 行向量与列向量: $\left( a_1,a_2,a_3,... \right)$$\begin{pmatrix} a_1 \\ a_2 \\ a_3 \end{pmatrix}$`,
    })
    const root = document.createElement('div')
    root.textContent = '![[target]]'

    await decorateWikiPreview(root, context())

    expect(root.querySelectorAll('.katex')).toHaveLength(2)
    expect(root.querySelector('.katex-error')).toBeNull()
    expect(root.textContent).not.toContain('ParseError')
  })

  it('embeds a local knowledge image through the existing raw-file endpoint', async () => {
    const root = document.createElement('div')
    root.textContent = '![[static/chart.png]]'

    await decorateWikiPreview(root, context())

    const image = root.querySelector<HTMLImageElement>('.wiki-embed-image')
    expect(image).not.toBeNull()
    expect(image?.src).toContain('/knowledge/files/raw')
    expect(knowledgeMocks.readKnowledgeFile).not.toHaveBeenCalled()
  })

  it('unfolds reciprocal-style recursion through five levels and then stops', async () => {
    knowledgeMocks.readKnowledgeFile.mockResolvedValue({ content: '循环 ![[loop]]' })
    const root = document.createElement('div')
    root.textContent = '![[loop]]'

    await decorateWikiPreview(root, context())

    expect(root.querySelectorAll('.wiki-embed')).toHaveLength(6)
    expect(root.querySelector('.wiki-embed-limit')?.textContent).toContain('5 层上限')
    expect(knowledgeMocks.readKnowledgeFile).toHaveBeenCalledTimes(1)
  })
})
