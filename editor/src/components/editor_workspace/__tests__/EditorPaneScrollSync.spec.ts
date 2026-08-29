/*
 * Markdown Split scroll synchronization regression tests.
 *
 * Usage:
 * Ensures wheel/scroll movement follows the source pane's normalized scroll
 * range instead of repeatedly anchoring to an unmoved caret position.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('EditorPane Markdown Split scroll synchronization', () => {
  it('maps editor scrolling by ratio rather than the stationary caret', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/editor_workspace/EditorPane.vue'), 'utf8')
    const handlerStart = source.indexOf('function handleEditorScroll')
    const handlerEnd = source.indexOf('function handleEditorCursor', handlerStart)
    const handler = source.slice(handlerStart, handlerEnd)

    expect(handlerStart).toBeGreaterThanOrEqual(0)
    expect(handler).toContain('syncMarkdownPreviewToRatio(payload.ratio)')
    expect(handler).not.toContain('syncMarkdownPreviewToCaret(payload)')
  })
})
