/*
 * Electron preload bridge for the editor renderer.
 *
 * Usage:
 * Exposes a small, typed-safe API under window.agentEditorDesktop without
 * enabling Node.js access in the Vue application.
 */
/* eslint-disable @typescript-eslint/no-require-imports */

const { contextBridge, ipcRenderer, webUtils } = require('electron')

contextBridge.exposeInMainWorld('agentEditorDesktop', {
  isDesktop: true,
  platform: process.platform,
  minimize: () => ipcRenderer.send('window:minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window:toggle-maximize'),
  beginWindowResize: (edge, screenX, screenY) => ipcRenderer.invoke('window:begin-resize', { edge, screenX, screenY }),
  updateWindowResize: (screenX, screenY) => ipcRenderer.send('window:resize-to', { screenX, screenY }),
  endWindowResize: () => ipcRenderer.send('window:end-resize'),
  onMaximizedChange: (callback) => {
    const handler = (_event, value) => callback(value)
    ipcRenderer.on('window:maximized-changed', handler)
    return () => ipcRenderer.removeListener('window:maximized-changed', handler)
  },
  close: () => ipcRenderer.send('window:close'),
  openExternal: (url) => ipcRenderer.invoke('shell:open-external', url),
  openPath: (path) => ipcRenderer.invoke('shell:open-path', path),
  showItemInFolder: (path) => ipcRenderer.invoke('shell:show-item-in-folder', path),
  selectDirectory: () => ipcRenderer.invoke('dialog:select-directory'),
  copyFilePaths: (paths, mode) => ipcRenderer.invoke('clipboard:write-files', paths, mode),
  readClipboardFiles: () => ipcRenderer.invoke('clipboard:read-files'),
  readClipboardFilePaths: async () => {
    const payload = await ipcRenderer.invoke('clipboard:read-files')
    return Array.isArray(payload?.paths) ? payload.paths : []
  },
  copyExternalPathsIntoDirectory: (paths, targetDir, mode, conflictStrategy) => ipcRenderer.invoke('files:copy-into-directory', paths, targetDir, mode, conflictStrategy),
  listFontFamilies: () => ipcRenderer.invoke('system:list-font-families'),
  getPathForFile: (file) => webUtils?.getPathForFile ? webUtils.getPathForFile(file) : (file?.path || ''),
  writeClipboardText: (text) => ipcRenderer.invoke('clipboard:write-text', text),
  // Floating window bridge.
  floatingSetBounds: (size) => ipcRenderer.invoke('floating:set-bounds', size),
  floatingSetAlwaysOnTop: (mode) => ipcRenderer.invoke('floating:set-always-on-top', mode),
  floatingClose: () => ipcRenderer.send('floating:close'),
  floatingSetVisible: (visible) => ipcRenderer.invoke('floating:set-visible', { visible }),
  floatingGetState: () => ipcRenderer.invoke('floating:get-state'),
  floatingToggle: () => ipcRenderer.send('floating:toggle'),
  // Cross-window sync: the main window broadcasts theme/session changes to the
  // floating window; the floating window subscribes with onWindowSync.
  windowSync: (type, value) => ipcRenderer.send('agent:window-sync', { type, value }),
  onWindowSync: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on('agent:window-sync', handler)
    return () => ipcRenderer.removeListener('agent:window-sync', handler)
  },
  // Open the full Agent page in the main window from the floating window.
  openAgentPage: () => ipcRenderer.send('floating:open-agent-page'),
  onOpenAgentPage: (callback) => {
    const handler = () => callback()
    ipcRenderer.on('agent:open-agent-page', handler)
    return () => ipcRenderer.removeListener('agent:open-agent-page', handler)
  },
})
