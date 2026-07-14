import { createRequire } from 'node:module'
import { describe, expect, it, vi } from 'vitest'

const require = createRequire(import.meta.url)
const { handleEditShortcut } = require('../../electron/edit-shortcuts.cjs') as {
  handleEditShortcut: (
    event: { preventDefault: () => void },
    input: Record<string, string | boolean>,
    webContents: Record<string, () => void>,
    commandModifier: string,
  ) => boolean
}

function createWebContents() {
  return {
    copy: vi.fn(),
    paste: vi.fn(),
    cut: vi.fn(),
    selectAll: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
  }
}

describe('Electron edit shortcuts', () => {
  it.each([
    ['Ctrl+Z', false],
    ['Ctrl+Shift+Z', true],
  ])('leaves %s for the renderer', (_label, shift) => {
    const preventDefault = vi.fn()
    const webContents = createWebContents()

    const handled = handleEditShortcut(
      { preventDefault },
      { control: true, key: 'z', shift },
      webContents,
      'control',
    )

    expect(handled).toBe(false)
    expect(preventDefault).not.toHaveBeenCalled()
    expect(webContents.undo).not.toHaveBeenCalled()
    expect(webContents.redo).not.toHaveBeenCalled()
  })

  it('keeps shell-level clipboard shortcuts working', () => {
    const preventDefault = vi.fn()
    const webContents = createWebContents()

    const handled = handleEditShortcut(
      { preventDefault },
      { control: true, key: 'c' },
      webContents,
      'control',
    )

    expect(handled).toBe(true)
    expect(webContents.copy).toHaveBeenCalledOnce()
    expect(preventDefault).toHaveBeenCalledOnce()
  })
})
