/*
 * Markdown outline regression tests.
 *
 * Verifies source parsing, nesting, fenced-code exclusion, filtering, and
 * current-heading resolution without involving the editor DOM.
 */
import { describe, expect, it } from 'vitest'

import {
  filterMarkdownOutline,
  flattenMarkdownOutline,
  headingAtOffset,
  parseMarkdownOutline,
} from '../markdownOutline'

describe('Markdown outline helpers', () => {
  const markdown = [
    '# Overview',
    'intro',
    '## Setup',
    'body',
    '```md',
    '### Not a heading',
    '```',
    '### Install',
    '# Appendix #',
  ].join('\n')

  it('builds source-ordered heading levels and ignores fenced code', () => {
    const outline = parseMarkdownOutline(markdown)

    expect(outline.map((item) => item.text)).toEqual(['Overview', 'Appendix'])
    expect(outline[0]?.children.map((item) => item.text)).toEqual(['Setup'])
    expect(outline[0]?.children[0]?.children.map((item) => item.text)).toEqual(['Install'])
    expect(flattenMarkdownOutline(outline).map((item) => item.text)).toEqual([
      'Overview', 'Setup', 'Install', 'Appendix',
    ])
  })

  it('keeps matching headings and their ancestor path', () => {
    const filtered = filterMarkdownOutline(parseMarkdownOutline(markdown), 'stall')

    expect(flattenMarkdownOutline(filtered).map((item) => item.text)).toEqual([
      'Overview', 'Setup', 'Install',
    ])
  })

  it('resolves the heading that owns the caret offset', () => {
    const outline = parseMarkdownOutline(markdown)

    expect(headingAtOffset(outline, markdown.indexOf('body'))?.text).toBe('Setup')
    expect(headingAtOffset(outline, markdown.indexOf('Appendix'))?.text).toBe('Appendix')
    expect(headingAtOffset(outline, -1)).toBeNull()
  })

  it('keeps a trailing hash when it is part of the heading text', () => {
    expect(parseMarkdownOutline('# C#\n# Closed heading ###').map((item) => item.text)).toEqual([
      'C#', 'Closed heading',
    ])
  })
})
