/*
 * Coordinate frameless main-window state changes with the native Windows move loop.
 *
 * Usage: call finishMainWindowRestore from BrowserWindow's `unmaximize` event.
 */

/**
 * Disable the temporary native resize frame only after drag-to-restore completes.
 * The maximized check prevents a queued restore callback from racing a new maximize.
 */
function finishMainWindowRestore(window, applyShape, defer = setImmediate) {
  defer(() => {
    if (!window || window.isDestroyed() || window.isMaximized()) {
      return
    }
    window.setResizable(false)
    applyShape()
  })
}

/**
 * Restore the pre-maximized size while keeping the grabbed titlebar point under the cursor.
 */
function boundsForMainDragRestore(maximizedBounds, normalBounds, screenX, screenY) {
  const horizontalAnchor = Math.min(
    Math.max((screenX - maximizedBounds.x) / maximizedBounds.width, 0),
    1,
  )
  const titlebarOffsetY = Math.max(screenY - maximizedBounds.y, 0)
  const x = Math.round(screenX - normalBounds.width * horizontalAnchor)
  const y = Math.round(screenY - titlebarOffsetY)
  return {
    bounds: { x, y, width: normalBounds.width, height: normalBounds.height },
    offsetX: screenX - x,
    offsetY: screenY - y,
  }
}

module.exports = { boundsForMainDragRestore, finishMainWindowRestore }
