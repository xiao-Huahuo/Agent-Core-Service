/*
 * Electron main process for the editor desktop shell.
 *
 * Usage:
 * - Development: npm run dev:electron
 * - Production preview: npm run build && npm run electron
 *
 * The BrowserWindow is intentionally frameless. Window controls are exposed to
 * the renderer through preload.cjs and rendered in TopCommandBar.vue.
 */
/* eslint-disable @typescript-eslint/no-require-imports */

const { app, BrowserWindow, clipboard, dialog, ipcMain, Menu, shell } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const { handleEditShortcut } = require('./edit-shortcuts.cjs')

const DEV_SERVER_URL = process.env.ELECTRON_RENDERER_URL || 'http://127.0.0.1:5173'

let mainWindow = null

function buildWindowsFileListBuffer(filePaths) {
  return Buffer.from(`${filePaths.join('\0')}\0\0`, 'utf16le')
}

function buildDropEffectBuffer(mode) {
  const effect = mode === 'cut' ? 2 : 1
  return Buffer.from([effect, 0, 0, 0])
}

function parseWindowsFileListBuffer(buffer) {
  if (!buffer || buffer.length === 0) {
    return []
  }
  return buffer.toString('utf16le').split('\0').map((item) => item.trim()).filter(Boolean)
}

function readClipboardDropEffect() {
  const buffer = clipboard.readBuffer('Preferred DropEffect')
  if (!buffer || buffer.length === 0) {
    return 'copy'
  }
  return buffer[0] === 2 ? 'cut' : 'copy'
}

function splitNameExtension(filename) {
  const extension = path.extname(filename)
  const stem = extension ? filename.slice(0, -extension.length) : filename
  return { stem, extension }
}

function uniqueChildPath(targetDir, preferredName) {
  const safeName = path.basename(preferredName).trim() || 'untitled'
  const firstPath = path.join(targetDir, safeName)
  if (!fs.existsSync(firstPath)) {
    return firstPath
  }
  const { stem, extension } = splitNameExtension(safeName)
  for (let index = 2; index < 1000; index += 1) {
    const candidate = path.join(targetDir, `${stem} ${index}${extension}`)
    if (!fs.existsSync(candidate)) {
      return candidate
    }
  }
  return path.join(targetDir, `${stem} ${Date.now()}${extension}`)
}

async function copyOrMovePath(sourcePath, targetPath, mode) {
  const sourceStat = await fs.promises.stat(sourcePath)
  if (sourceStat.isDirectory()) {
    await fs.promises.cp(sourcePath, targetPath, { recursive: true, errorOnExist: true })
  } else {
    await fs.promises.copyFile(sourcePath, targetPath, fs.constants.COPYFILE_EXCL)
  }
  if (mode === 'cut') {
    await fs.promises.rm(sourcePath, { recursive: true, force: true })
  }
}

function readClipboardFilePayload() {
  const filePaths = process.platform === 'win32'
    ? parseWindowsFileListBuffer(clipboard.readBuffer('FileNameW'))
    : clipboard.readText().split(/\r?\n/u).map((item) => item.trim()).filter(Boolean)
  return {
    mode: readClipboardDropEffect(),
    paths: filePaths.filter((item) => fs.existsSync(item)),
  }
}

function isDevelopment() {
  return !app.isPackaged && process.env.ELECTRON_FORCE_PROD !== 'true'
}

function shouldOpenDevTools() {
  return process.env.ELECTRON_OPEN_DEVTOOLS === 'true'
}

async function loadDevServer(window, attempts = 40) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      await window.loadURL(DEV_SERVER_URL)
      return
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
  await window.loadURL(DEV_SERVER_URL)
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 960,
    minHeight: 640,
    frame: false,
    show: false,
    backgroundColor: '#101010',
    title: 'AgentService Editor',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // Register shell-level clipboard shortcuts. Undo/redo must reach the renderer
  // because Vditor owns its history stack.
  const ctrlKey = process.platform === 'darwin' ? 'meta' : 'control'
  mainWindow.webContents.on('before-input-event', (event, input) => {
    handleEditShortcut(event, input, mainWindow.webContents, ctrlKey)
  })

  if (isDevelopment()) {
    void loadDevServer(mainWindow)
    if (shouldOpenDevTools()) {
      mainWindow.webContents.openDevTools({ mode: 'detach' })
    }
  } else {
    void mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

app.whenReady().then(() => {
  createMainWindow()

  // Keep clipboard roles available without claiming renderer-owned history keys.
  const template = [
    {
      label: 'Edit',
      submenu: [
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

ipcMain.on('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.handle('window:toggle-maximize', () => {
  if (!mainWindow) {
    return false
  }
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize()
    return false
  }
  mainWindow.maximize()
  return true
})

ipcMain.on('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('shell:open-external', async (_event, url) => {
  if (typeof url === 'string' && /^https?:\/\//u.test(url)) {
    await shell.openExternal(url)
  }
})

ipcMain.handle('shell:open-path', async (_event, filePath) => {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    return ''
  }
  try {
    return await shell.openPath(filePath)
  } catch {
    return 'error'
  }
})

ipcMain.handle('shell:show-item-in-folder', async (_event, filePath) => {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    return
  }
  shell.showItemInFolder(filePath)
})

ipcMain.handle('dialog:select-directory', async () => {
  if (!mainWindow) {
    return ''
  }
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  })
  if (result.canceled || result.filePaths.length === 0) {
    return ''
  }
  return result.filePaths[0]
})

ipcMain.handle('clipboard:write-text', async (_event, text) => {
  if (typeof text !== 'string' || !text.trim()) {
    return false
  }
  clipboard.writeText(text)
  return true
})

ipcMain.handle('clipboard:write-files', async (_event, filePaths, mode) => {
  if (!Array.isArray(filePaths) || filePaths.length === 0) {
    return false
  }
  const normalizedPaths = filePaths.filter((item) => typeof item === 'string' && item.trim())
  if (normalizedPaths.length === 0) {
    return false
  }
  clipboard.writeText(normalizedPaths.join('\n'))
  if (process.platform === 'win32') {
    clipboard.writeBuffer('FileNameW', buildWindowsFileListBuffer(normalizedPaths))
    clipboard.writeBuffer('Preferred DropEffect', buildDropEffectBuffer(mode))
  }
  return true
})

ipcMain.handle('clipboard:read-files', async () => readClipboardFilePayload())

ipcMain.handle('files:copy-into-directory', async (_event, sourcePaths, targetDir, mode) => {
  if (!Array.isArray(sourcePaths) || typeof targetDir !== 'string' || !targetDir.trim()) {
    return { ok: false, paths: [] }
  }
  await fs.promises.mkdir(targetDir, { recursive: true })
  const copiedPaths = []
  for (const sourcePath of sourcePaths) {
    if (typeof sourcePath !== 'string' || !sourcePath.trim() || !fs.existsSync(sourcePath)) {
      continue
    }
    const targetPath = uniqueChildPath(targetDir, path.basename(sourcePath))
    await copyOrMovePath(sourcePath, targetPath, mode === 'cut' ? 'cut' : 'copy')
    copiedPaths.push(targetPath)
  }
  return { ok: copiedPaths.length > 0, paths: copiedPaths }
})
