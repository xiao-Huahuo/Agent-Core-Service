/*
 * Handle only shortcuts that need explicit support in the frameless Electron
 * shell. Undo and redo intentionally stay in the renderer so rich editors can
 * use their own history implementation.
 */

const EDIT_COMMANDS = {
  c: 'copy',
  v: 'paste',
  x: 'cut',
  a: 'selectAll',
}

function handleEditShortcut(event, input, webContents, commandModifier) {
  if (!input[commandModifier]) {
    return false
  }

  const command = EDIT_COMMANDS[input.key]
  if (!command) {
    return false
  }

  webContents[command]()
  event.preventDefault()
  return true
}

module.exports = { handleEditShortcut }
