import { describe, expect, it } from 'vitest'

import { resolveEditorFilePipeline } from '@/utils/editorFilePipeline'

describe('resolveEditorFilePipeline', () => {
  it.each([
    ['note.md', ['edit', 'preview', 'split'], 'edit', false, true],
    ['note.txt', ['text'], 'text', false, true],
    ['sheet.xlsx', ['forms'], 'forms', true, false],
    ['legacy.xls', ['forms'], 'forms', true, false],
    ['data.csv', ['text', 'forms'], 'text', true, true],
    ['report.docx', ['preview', 'markdown'], 'preview', true, false],
    ['scan.pdf', ['preview', 'markdown'], 'preview', true, false],
    ['slides.pptx', ['preview', 'markdown'], 'preview', true, false],
    ['photo.png', ['preview', 'markdown'], 'preview', true, false],
    ['clip.mp4', ['preview'], 'preview', true, false],
    ['recording.webm', ['preview'], 'preview', true, false],
    ['script.py', ['code'], 'code', false, true],
    ['paper.tex', ['code', 'preview', 'split'], 'code', false, true],
    ['legacy.doc', ['binary'], 'binary', true, false],
  ])('%s resolves its complete editor contract', (path, modes, defaultMode, usesPreview, editable) => {
    const pipeline = resolveEditorFilePipeline(path)

    expect(pipeline.modes.map((item) => item.mode)).toEqual(modes)
    expect(pipeline.defaultMode).toBe(defaultMode)
    expect(pipeline.usesPreviewEndpoint).toBe(usesPreview)
    expect(pipeline.editable).toBe(editable)
  })

  it('promotes an unsupported UTF-8 file to Text after backend classification', () => {
    expect(resolveEditorFilePipeline('README.weird', 'text').modes.map((item) => item.mode)).toEqual(['text'])
  })

  it('keeps an unsupported binary file in Binary', () => {
    expect(resolveEditorFilePipeline('archive.weird', 'unsupported').modes.map((item) => item.mode)).toEqual(['binary'])
  })
})
