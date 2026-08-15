/*
 * Regression checks for the frameless Electron main-window state transition.
 *
 * Usage: run with `npm run test:unit -- src/__tests__/mainWindowState.spec.ts`.
 */
import { createRequire } from 'node:module'
import { describe, expect, it, vi } from 'vitest'

const require = createRequire(import.meta.url)
const { boundsForMainDragRestore, finishMainWindowRestore } = require('../../electron/main-window-state.cjs') as {
  boundsForMainDragRestore: (
    maximizedBounds: { x: number; y: number; width: number; height: number },
    normalBounds: { x: number; y: number; width: number; height: number },
    screenX: number,
    screenY: number,
  ) => { bounds: { x: number; y: number; width: number; height: number }; offsetX: number; offsetY: number }
  finishMainWindowRestore: (
    window: { isDestroyed: () => boolean; isMaximized: () => boolean; setResizable: (value: boolean) => void },
    applyShape: () => void,
    defer: (callback: () => void) => void,
  ) => void
}

describe('Electron main-window restore', () => {
  it('restores the saved normal size under the grabbed titlebar point', () => {
    const restored = boundsForMainDragRestore(
      { x: 0, y: 0, width: 2560, height: 1392 },
      { x: 500, y: 240, width: 1440, height: 920 },
      1280,
      18,
    )

    expect(restored).toEqual({
      bounds: { x: 560, y: 0, width: 1440, height: 920 },
      offsetX: 720,
      offsetY: 18,
    })
  })

  it('keeps the native resize frame until Windows finishes drag-to-restore', () => {
    const deferred: Array<() => void> = []
    const window = {
      isDestroyed: vi.fn(() => false),
      isMaximized: vi.fn(() => false),
      setResizable: vi.fn(),
    }
    const applyShape = vi.fn()

    finishMainWindowRestore(window, applyShape, (callback) => deferred.push(callback))

    expect(window.setResizable).not.toHaveBeenCalled()
    expect(applyShape).not.toHaveBeenCalled()

    deferred[0]?.()

    expect(window.setResizable).toHaveBeenCalledWith(false)
    expect(applyShape).toHaveBeenCalledOnce()
  })
})
