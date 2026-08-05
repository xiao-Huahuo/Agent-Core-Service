/// <reference types="vite/client" />

declare module '@fontsource/jetbrains-mono'

interface AgentEditorDesktopApi {
  isDesktop: boolean
  platform: NodeJS.Platform
  minimize: () => void
  toggleMaximize: () => Promise<boolean>
  onMaximizedChange: (callback: (maximized: boolean) => void) => () => void
  close: () => void
  openExternal: (url: string) => Promise<void>
  selectDirectory: () => Promise<string>
  copyFilePaths: (paths: string[], mode: 'copy' | 'cut') => Promise<boolean>
  readClipboardFiles: () => Promise<{ mode: 'copy' | 'cut'; paths: string[] }>
  readClipboardFilePaths: () => Promise<string[]>
  copyExternalPathsIntoDirectory: (
    paths: string[],
    targetDir: string,
    mode: 'copy' | 'cut',
    conflictStrategy?: 'overwrite' | 'skip' | 'rename',
  ) => Promise<{ ok: boolean; paths: string[] }>
  listFontFamilies: () => Promise<string[]>
  getPathForFile: (file: File) => string
  writeClipboardText: (text: string) => Promise<boolean>
  openPath: (path: string) => Promise<string>
  showItemInFolder: (path: string) => Promise<void>
  floatingSetBounds: (size: { width: number; height: number }) => Promise<boolean>
  floatingSetAlwaysOnTop: (mode: 'off' | 'normal' | 'global') => Promise<boolean>
  floatingClose: () => void
  floatingSetVisible: (visible: boolean) => Promise<boolean>
  floatingGetState: () => Promise<{ visible: boolean; pinMode?: string }>
  floatingToggle: () => void
  windowSync: (type: string, value: string | null) => void
  onWindowSync: (callback: (payload: { type: string; value: string | null }) => void) => () => void
}

interface Window {
  agentEditorDesktop?: AgentEditorDesktopApi
}
