/*
 * EditorPane LaTeX load-before-save contract.
 *
 * Usage:
 * Protects the real UI bug where an immediate Split click saved empty content
 * before the asynchronous file read completed.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('EditorPane LaTeX compilation ordering', () => {
  it('waits for active file loading before saving and compiling', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/editor_workspace/EditorPane.vue'), 'utf8')
    const compileStart = source.indexOf('async function compileActiveLatex')
    const waitForLoad = source.indexOf('while (workspaceStore.isFileLoading', compileStart)
    const saveSource = source.indexOf('if (save) await workspaceStore.saveActiveFile()', compileStart)
    const compileRequest = source.indexOf('latexCompileResult.value = await compileLatexFile(', compileStart)

    expect(compileStart).toBeGreaterThanOrEqual(0)
    expect(waitForLoad).toBeGreaterThan(compileStart)
    expect(saveSource).toBeGreaterThan(waitForLoad)
    expect(compileRequest).toBeGreaterThan(saveSource)
  })
})
