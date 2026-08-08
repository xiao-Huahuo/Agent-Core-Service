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

const { app, BrowserWindow, clipboard, dialog, ipcMain, Menu, shell, Tray, nativeImage } = require('electron')
const childProcess = require('node:child_process')
const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')
const { handleEditShortcut } = require('./edit-shortcuts.cjs')

const DEV_SERVER_URL = process.env.ELECTRON_RENDERER_URL || 'http://127.0.0.1:5173'
const BACKEND_SERVER_URL = process.env.METAWEAVE_BACKEND_URL || 'http://127.0.0.1:8002'
const APP_ICON_FILENAME = process.platform === 'darwin' ? 'app.icns' : 'app.ico'
const APP_ICON_PATH = path.join(__dirname, '..', 'src', 'assets', 'icons', APP_ICON_FILENAME)

app.setName('MetaWeave')

let mainWindow = null
let tray = null
let floatingWindow = null
let backendProcess = null

/** Resolve the window that owns a given IPC event, falling back to mainWindow. */
function windowFromEvent(event) {
  return BrowserWindow.fromWebContents(event.sender) || mainWindow
}

function buildDropEffectBuffer(mode) {
  const effect = mode === 'cut' ? 2 : 1
  return Buffer.from([effect, 0, 0, 0])
}

function writeWindowsFileClipboard(filePaths, mode) {
  const payload = Buffer.from(JSON.stringify(filePaths), 'utf8').toString('base64')
  const effect = mode === 'cut' ? 2 : 1
  const script = `
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($env:METAWEAVE_CLIPBOARD_FILES_B64))
$paths = ConvertFrom-Json -InputObject $json
$files = New-Object System.Collections.Specialized.StringCollection
foreach ($item in $paths) {
  if ([string]::IsNullOrWhiteSpace([string]$item)) { continue }
  [void]$files.Add([string]$item)
}
if ($files.Count -le 0) { throw 'empty file drop list' }
$data = New-Object System.Windows.Forms.DataObject
$data.SetFileDropList($files)
$effectBytes = [byte[]](${effect}, 0, 0, 0)
$effectStream = New-Object System.IO.MemoryStream
$effectStream.Write($effectBytes, 0, $effectBytes.Length)
$effectStream.Position = 0
$data.SetData('Preferred DropEffect', $effectStream)
[System.Windows.Forms.Clipboard]::SetDataObject($data, $true, 10, 100)
`
  return new Promise((resolve) => {
    const child = childProcess.spawn(
      'powershell.exe',
      ['-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-Command', script],
      {
        env: {
          ...process.env,
          METAWEAVE_CLIPBOARD_FILES_B64: payload,
        },
        windowsHide: true,
      },
    )
    let stderr = ''
    child.stderr.on('data', (chunk) => {
      stderr += String(chunk)
    })
    child.on('error', () => resolve(false))
    child.on('close', (code) => {
      if (code !== 0 && stderr.trim()) {
        console.warn('writeWindowsFileClipboard failed:', stderr.trim())
      }
      resolve(code === 0)
    })
  })
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
  for (let index = 1; index < 1000; index += 1) {
    const candidate = path.join(targetDir, `${stem} (${index})${extension}`)
    if (!fs.existsSync(candidate)) {
      return candidate
    }
  }
  return path.join(targetDir, `${stem} ${Date.now()}${extension}`)
}

async function copyOrMovePath(sourcePath, targetPath, mode) {
  const sourceStat = await fs.promises.stat(sourcePath)
  if (sourceStat.isDirectory()) {
    await fs.promises.cp(sourcePath, targetPath, { recursive: true, force: true })
  } else {
    await fs.promises.copyFile(sourcePath, targetPath)
  }
  if (mode === 'cut') {
    await fs.promises.rm(sourcePath, { recursive: true, force: true })
  }
}

function readClipboardFilePayload() {
  let filePaths = []
  let mode = 'copy'

  // Electron 15+ native clipboard API reads CF_HDROP correctly.
  if (typeof clipboard.readFiles === 'function') {
    try {
      const files = clipboard.readFiles()
      filePaths = files.filter((f) => f.path).map((f) => f.path)
    } catch {
      filePaths = []
    }
  }

  // Fallback: parse FileNameW buffer manually (older Electron or non-Windows).
  if (filePaths.length === 0) {
    filePaths = clipboard.readText().split(/\r?\n/u).map((item) => item.trim()).filter(Boolean)
  }

  mode = readClipboardDropEffect()

  return {
    mode,
    paths: filePaths.filter((item) => fs.existsSync(item)),
  }
}

function listWindowsFontFamilies() {
  const script = `
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$fonts = (New-Object System.Drawing.Text.InstalledFontCollection).Families |
  ForEach-Object { $_.Name } |
  Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
  Sort-Object -Unique
$json = $fonts | ConvertTo-Json -Compress
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
`
  return new Promise((resolve) => {
    const child = childProcess.spawn(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
      { windowsHide: true },
    )
    let stdout = ''
    child.stdout.on('data', (chunk) => {
      stdout += String(chunk)
    })
    child.on('error', () => resolve([]))
    child.on('close', (code) => {
      if (code !== 0 || !stdout.trim()) {
        resolve([])
        return
      }
      try {
        const json = Buffer.from(stdout.trim(), 'base64').toString('utf8')
        const payload = JSON.parse(json)
        resolve(Array.isArray(payload) ? payload : [payload])
      } catch {
        resolve([])
      }
    })
  })
}

function listUnixFontFamilies() {
  return new Promise((resolve) => {
    const child = childProcess.spawn('fc-list', [':', 'family'], { windowsHide: true })
    let stdout = ''
    child.stdout.on('data', (chunk) => {
      stdout += String(chunk)
    })
    child.on('error', () => resolve([]))
    child.on('close', (code) => {
      if (code !== 0) {
        resolve([])
        return
      }
      const fonts = stdout
        .split(/\r?\n/u)
        .flatMap((line) => line.split(','))
        .map((item) => item.trim())
        .filter(Boolean)
      resolve([...new Set(fonts)].sort((a, b) => a.localeCompare(b)))
    })
  })
}

function isDevelopment() {
  return !app.isPackaged && process.env.ELECTRON_FORCE_PROD !== 'true'
}

function shouldOpenDevTools() {
  return process.env.ELECTRON_OPEN_DEVTOOLS === 'true'
}

function waitForServerUrl(serverUrl, attempts = 80, intervalMs = 250) {
  // 轮询 TCP 端口而不是拿 loadURL 失败当探测手段:连接被拒时 Chromium 会
  // 向终端刷 ERR_CONNECTION_REFUSED,且不受 catch 控制。端口探测成功后才真正加载。
  const url = new URL(serverUrl)
  const port = Number(url.port || 80)
  return new Promise((resolve) => {
    let count = 0
    const tryConnect = () => {
      const socket = net.connect(port, url.hostname)
      socket.once('connect', () => {
        socket.destroy()
        resolve()
      })
      socket.once('error', () => {
        socket.destroy()
        count += 1
        if (count >= attempts) {
          resolve()
        } else {
          setTimeout(tryConnect, intervalMs)
        }
      })
    }
    tryConnect()
  })
}

function waitForDevServer(attempts = 80, intervalMs = 250) {
  return waitForServerUrl(DEV_SERVER_URL, attempts, intervalMs)
}

async function loadDevServer(window, query) {
  await waitForDevServer()
  const url = query
    ? `${DEV_SERVER_URL}?${new URLSearchParams(query).toString()}`
    : DEV_SERVER_URL
  await window.loadURL(url)
}

function packagedBackendPath() {
  return path.join(process.resourcesPath, 'backend', 'AgentService.exe')
}

function packagedDefaultResourcesPath() {
  return path.join(process.resourcesPath, 'default-resources')
}

function userProjectRoot() {
  return app.getPath('userData')
}

function copyMissing(source, target) {
  if (!fs.existsSync(source) || fs.existsSync(target)) {
    return
  }
  fs.cpSync(source, target, { recursive: true })
}

function ensurePackagedUserResources() {
  if (!app.isPackaged) {
    return userProjectRoot()
  }
  const projectRoot = userProjectRoot()
  const resourcesRoot = path.join(projectRoot, 'resources')
  const defaultsRoot = packagedDefaultResourcesPath()

  fs.mkdirSync(path.join(resourcesRoot, 'knowledge'), { recursive: true })
  fs.mkdirSync(path.join(resourcesRoot, 'mcp'), { recursive: true })
  copyMissing(path.join(defaultsRoot, 'mcp', 'example.json'), path.join(resourcesRoot, 'mcp', 'example.json'))
  copyMissing(path.join(defaultsRoot, 'safety'), path.join(resourcesRoot, 'safety'))
  copyMissing(path.join(defaultsRoot, 'skills'), path.join(resourcesRoot, 'skills'))

  return projectRoot
}

async function startPackagedBackend() {
  if (!app.isPackaged || process.platform !== 'win32') {
    return
  }
  if (await isTcpServerReady(BACKEND_SERVER_URL)) {
    return
  }
  const backendExe = packagedBackendPath()
  if (!fs.existsSync(backendExe)) {
    dialog.showErrorBox('MetaWeave 后端缺失', `未找到内置后端: ${backendExe}`)
    app.quit()
    return
  }
  const projectRoot = ensurePackagedUserResources()
  backendProcess = childProcess.spawn(backendExe, [], {
    cwd: projectRoot,
    detached: false,
    env: {
      ...process.env,
      AGENT_PROJECT_ROOT: projectRoot,
      AGENT_BASE_DATA_DIR: path.join(projectRoot, 'runtime'),
    },
    stdio: 'ignore',
    windowsHide: true,
  })
  backendProcess.once('error', (error) => {
    dialog.showErrorBox('MetaWeave 后端启动失败', String(error))
    app.quit()
  })
  backendProcess.once('exit', () => {
    backendProcess = null
  })
}

function isTcpServerReady(serverUrl) {
  const url = new URL(serverUrl)
  const port = Number(url.port || 80)
  return new Promise((resolve) => {
    const socket = net.connect(port, url.hostname)
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('error', () => {
      socket.destroy()
      resolve(false)
    })
  })
}

async function loadPackagedBackend(window, query) {
  await waitForServerUrl(BACKEND_SERVER_URL, 240, 500)
  const url = query
    ? `${BACKEND_SERVER_URL}?${new URLSearchParams(query).toString()}`
    : BACKEND_SERVER_URL
  await window.loadURL(url)
}

function createTray() {
  const icon = nativeImage.createFromPath(APP_ICON_PATH)
  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('MetaWeave')

  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus()
      } else {
        mainWindow.show()
        mainWindow.focus()
      }
    }
  })

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示 / Show',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      },
    },
    {
      label: '悬浮窗 / Floating',
      click: () => {
        toggleFloatingWindow()
      },
    },
    { type: 'separator' },
    {
      label: '退出 / Quit',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ])
  tray.setContextMenu(contextMenu)
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    frame: false,
    transparent: true,
    // 透明窗口默认仍带系统阴影,Windows 会在四角绘制直角的半透明阴影边框,
    // 与 CSS 圆角不匹配(暗色下明显)。关闭阴影让四角真正透明。
    hasShadow: false,
    // Windows 关键约束:可调整大小的 frameless 窗口必须保留 WS_THICKFRAME 样式
    // 才能从边缘拖拽改尺寸,该样式会强制窗口带一圈系统装饰(雾化/阴影"隔层",
    // 暗色下可见),并让 thickFrame:false 失效。与悬浮窗完全一致:resizable:false
    // + thickFrame:false 改用 WS_POPUP,彻底去掉这层装饰。代价:主窗口不再支持
    // 从边缘拖拽调整大小,改为最大化/还原按钮控制。
    resizable: false,
    thickFrame: false,
    // 必须显式全透明:Electron 未设置 backgroundColor 时窗口默认绘制白色,
    // 暗色模式下 #app 圆角裁剪掉的四角会露出白色直角层
    backgroundColor: '#00000000',
    show: false,
    title: 'AgentService Editor',
    icon: APP_ICON_PATH,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  // 最大化时窗口铺满工作区,shape 内缩会让四边露出 1px 桌面,故最大化
  // 清除 shape;非最大化时裁掉 DWM 边缘线。
  const applyMainWindowShape = () => {
    if (mainWindow.isDestroyed()) return
    if (mainWindow.isMaximized()) {
      mainWindow.setShape([])
    } else {
      applyTransparentShape(mainWindow)
    }
  }

  mainWindow.once('ready-to-show', () => {
    // 运行时兜底:部分 Windows 构建下构造参数里的透明背景不生效,
    // 圆角裁剪掉的四角会残留窗口默认白色直角层
    mainWindow.setBackgroundColor('#00000000')
    applyMainWindowShape()
    mainWindow.show()
  })

  // Notify the renderer about maximize state so the window corner radius can
  // be dropped while maximized (transparent corners would otherwise show through).
  const sendMaximizedState = () => {
    if (!mainWindow.isDestroyed()) {
      mainWindow.webContents.send('window:maximized-changed', mainWindow.isMaximized())
    }
  }
  mainWindow.on('maximize', () => {
    sendMaximizedState()
    applyMainWindowShape()
  })
  mainWindow.on('unmaximize', () => {
    sendMaximizedState()
    applyMainWindowShape()
  })
  // setShape 区域是绝对像素,窗口 resize(拖动)后必须重新套用
  mainWindow.on('resize', applyMainWindowShape)

  createTray()

  // Override close to hide to tray instead of quitting.
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
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
    void loadPackagedBackend(mainWindow)
  }
}

const FLOATING_DEFAULT_WIDTH = 460
const FLOATING_DEFAULT_HEIGHT = 172
const FLOATING_CHAT_HEIGHT = 600

// Windows 透明无边框窗口在矩形边缘仍会残留一条 1px 边框线(暗色下可见,
// 直角的、紧贴窗口矩形)。thickFrame: false 对这种 DWM/Chromium 绘制无效。
// 用 setShape 把窗口绘制区域内缩 1px,从原生层直接裁掉这条线。
// 悬浮窗卡片是 20px margin、阴影最大扩散 10px;主窗口内容四周有留白,
// 内缩 1px 不会影响任何内容。
function applyTransparentShape(win) {
  if (process.platform !== 'win32' || !win || win.isDestroyed()) {
    return
  }
  const [width, height] = win.getSize()
  win.setShape([
    { x: 1, y: 1, width: Math.max(width - 2, 1), height: Math.max(height - 2, 1) },
  ])
}

function createFloatingWindow() {
  if (floatingWindow && !floatingWindow.isDestroyed()) {
    return floatingWindow
  }
  floatingWindow = new BrowserWindow({
    width: FLOATING_DEFAULT_WIDTH,
    height: FLOATING_DEFAULT_HEIGHT,
    frame: false,
    transparent: true,
    hasShadow: false,
    // Windows 上无边框窗口默认仍用 WS_THICKFRAME 样式,会保留一圈系统
    // 描边线(暗色透明窗口下露出直角细线)。关闭它改为 WS_POPUP,去掉这条线。
    thickFrame: false,
    backgroundColor: '#00000000',
    show: false,
    skipTaskbar: true,
    resizable: false,
    title: 'MetaWeave Floating',
    icon: APP_ICON_PATH,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  floatingWindow.once('ready-to-show', () => {
    floatingWindow.setBackgroundColor('#00000000')
    applyTransparentShape(floatingWindow)
    floatingWindow.showInactive()
  })

  // Close hides the floating window instead of destroying it.
  floatingWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      floatingWindow.hide()
    }
  })

  if (isDevelopment()) {
    void loadDevServer(floatingWindow, { floating: '1' })
    if (shouldOpenDevTools()) {
      floatingWindow.webContents.openDevTools({ mode: 'detach' })
    }
  } else {
    void loadPackagedBackend(floatingWindow, { floating: '1' })
  }
  return floatingWindow
}

function toggleFloatingWindow() {
  const win = createFloatingWindow()
  if (win.isVisible()) {
    win.hide()
  } else {
    win.showInactive()
  }
}

app.whenReady().then(async () => {
  await startPackagedBackend()
  createMainWindow()
  // 悬浮窗随主窗口同步启动。
  createFloatingWindow()

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
  // Close hides to tray instead of quitting.
})

app.on('will-quit', () => {
  if (tray) {
    tray.destroy()
    tray = null
  }
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})

ipcMain.on('window:minimize', (event) => {
  windowFromEvent(event)?.minimize()
})

ipcMain.handle('window:toggle-maximize', (event) => {
  const win = windowFromEvent(event)
  if (!win) {
    return false
  }
  if (win.isMaximized()) {
    win.unmaximize()
    return false
  }
  win.maximize()
  return true
})

ipcMain.handle('system:list-font-families', async () => {
  const fonts = process.platform === 'win32'
    ? await listWindowsFontFamilies()
    : await listUnixFontFamilies()
  return fonts
    .map((item) => String(item).trim())
    .filter(Boolean)
})

ipcMain.on('window:close', (event) => {
  windowFromEvent(event)?.close()
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

ipcMain.handle('dialog:select-directory', async (event) => {
  const win = windowFromEvent(event)
  if (!win) {
    return ''
  }
  const result = await dialog.showOpenDialog(win, {
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
  const normalizedPaths = filePaths
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => path.resolve(item))
    .filter((item) => fs.existsSync(item))
  if (normalizedPaths.length === 0) {
    return false
  }

  if (process.platform === 'win32') {
    const ok = await writeWindowsFileClipboard(normalizedPaths, mode)
    if (ok) {
      return true
    }
  }

  if (typeof clipboard.writeFiles === 'function') {
    clipboard.writeFiles(normalizedPaths)
  } else {
    clipboard.writeText(normalizedPaths.join('\n'))
  }

  // PreferredDropEffect signals whether this was a copy or cut.
  if (mode === 'cut') {
    clipboard.writeBuffer('Preferred DropEffect', buildDropEffectBuffer(mode))
  }

  return true
})

ipcMain.handle('clipboard:read-files', async () => readClipboardFilePayload())

ipcMain.handle('files:copy-into-directory', async (_event, sourcePaths, targetDir, mode, conflictStrategy = 'rename') => {
  if (!Array.isArray(sourcePaths) || typeof targetDir !== 'string' || !targetDir.trim()) {
    return { ok: false, paths: [] }
  }
  await fs.promises.mkdir(targetDir, { recursive: true })
  const copiedPaths = []
  for (const sourcePath of sourcePaths) {
    if (typeof sourcePath !== 'string' || !sourcePath.trim() || !fs.existsSync(sourcePath)) {
      continue
    }
    const preferredPath = path.join(targetDir, path.basename(sourcePath))
    const exists = fs.existsSync(preferredPath)
    if (exists && conflictStrategy === 'skip') {
      continue
    }
    const targetPath = exists && conflictStrategy === 'rename'
      ? uniqueChildPath(targetDir, path.basename(sourcePath))
      : preferredPath
    if (exists && conflictStrategy === 'overwrite') {
      await fs.promises.rm(targetPath, { recursive: true, force: true })
    }
    await copyOrMovePath(sourcePath, targetPath, mode === 'cut' ? 'cut' : 'copy')
    copiedPaths.push(targetPath)
  }
  return { ok: copiedPaths.length > 0, paths: copiedPaths }
})

/* ---- Floating window IPC ---- */

ipcMain.handle('floating:set-bounds', (event, size) => {
  const win = windowFromEvent(event)
  if (!win || win !== floatingWindow) {
    return false
  }
  const width = Number.isFinite(size?.width) ? size.width : FLOATING_DEFAULT_WIDTH
  const height = Number.isFinite(size?.height) ? size.height : FLOATING_DEFAULT_HEIGHT
  const bounds = win.getBounds()
  win.setBounds({ x: bounds.x, y: bounds.y, width, height })
  // setShape 区域是绝对像素,窗口 resize 后必须重新套用,否则边缘线会回来
  applyTransparentShape(floatingWindow)
  return true
})

ipcMain.handle('floating:set-always-on-top', (event, mode) => {
  const win = windowFromEvent(event)
  if (!win || win !== floatingWindow) {
    return false
  }
  if (mode === 'global') {
    win.setAlwaysOnTop(true, 'screen-saver')
  } else if (mode === 'normal') {
    win.setAlwaysOnTop(true, 'normal')
  } else {
    win.setAlwaysOnTop(false)
  }
  return true
})

ipcMain.on('floating:close', (event) => {
  const win = windowFromEvent(event)
  if (win && win === floatingWindow) {
    win.close()
  }
})

ipcMain.handle('floating:set-visible', (_event, options) => {
  if (!floatingWindow || floatingWindow.isDestroyed()) {
    return false
  }
  if (options?.visible) {
    floatingWindow.showInactive()
  } else {
    floatingWindow.hide()
  }
  return true
})

ipcMain.handle('floating:get-state', () => {
  if (!floatingWindow || floatingWindow.isDestroyed()) {
    return { visible: false, pinMode: 'off' }
  }
  return { visible: floatingWindow.isVisible() }
})

ipcMain.on('floating:toggle', () => {
  toggleFloatingWindow()
})

// Forward theme / session changes from the main window to the floating window.
// localStorage storage events do not cross Electron BrowserWindows, so sync
// happens over IPC instead.
ipcMain.on('agent:window-sync', (event, payload) => {
  if (!floatingWindow || floatingWindow.isDestroyed()) {
    return
  }
  // Ignore echoes coming back from the floating window itself to avoid a loop.
  const sender = BrowserWindow.fromWebContents(event.sender)
  if (sender === floatingWindow) {
    return
  }
  const { type, value } = payload || {}
  if (type === 'theme' || type === 'session') {
    floatingWindow.webContents.send('agent:window-sync', { type, value })
  }
})

// Floating "Expand Agent page" → bring the main window forward and switch it
// to the Agent view. The main window renderer subscribes via onOpenAgentPage.
ipcMain.on('floating:open-agent-page', () => {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore()
  }
  mainWindow.show()
  mainWindow.focus()
  mainWindow.webContents.send('agent:open-agent-page')
})
