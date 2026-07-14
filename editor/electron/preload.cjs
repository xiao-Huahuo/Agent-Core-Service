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
  getPathForFile: (file) => webUtils?.getPathForFile ? webUtils.getPathForFile(file) : (file?.path || ''),
  writeClipboardText: (text) => ipcRenderer.invoke('clipboard:write-text', text),
})
