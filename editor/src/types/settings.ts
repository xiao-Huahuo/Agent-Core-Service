/*
 * Settings DTOs for the editor front-end.
 *
 * Usage:
 * These types mirror the future persisted user settings endpoints while the
 * current front-end keeps data in localStorage.
 */

/** Theme mode applied to documentElement. */
export type ThemeMode = 'dark' | 'light' | 'system'

/** Left workspace sidebar display density. */
export type SidebarDisplayMode = 'icons' | 'management'

/** Persisted editor profile settings. */
export interface UserSettingsProfile {
  /** Stable user identifier shared with the existing console front-end. */
  userId: string
  /** Local absolute path of the knowledge root. */
  knowledgeDir: string
  /** Active backend knowledge library id. */
  activeLibraryId: string
  /** Known backend knowledge library configs for this user. */
  knowledgeLibraries: KnowledgeLibraryProfile[]
  /** Whether the future watchdog bridge should push live file events. */
  knowledgeWatchEnabled: boolean
  /** Proxy URL for internet access (e.g. http://127.0.0.1:7890). */
  proxyUrl?: string
  /** Whether web search is enabled for the current user. */
  webSearchEnabled?: boolean
  /** Maximum results per web search call. */
  webSearchMaxResults?: number
  /** Whether uploaded files should be ingested immediately. Defaults to false. */
  autoIngestOnUpload?: boolean
  /** Whether OCR should be enabled after restarting the backend service. */
  ocrEnabled?: boolean
  /** Gitignore-like rules for files that must never enter the vector store. */
  knowledgeIgnorePatterns?: string
  /** Effective backend file suffixes that can enter the knowledge store. */
  knowledgeSupportedSuffixes?: string[]
  /** Agent terminal sandbox configuration cached from backend settings. */
  terminalSandbox?: unknown
  /** Optional font families prepended to the global UI font stack. */
  uiFontFamilies?: string[]
  /** Optional font families prepended to markdown/text document surfaces. */
  textFontFamilies?: string[]
  /** Global font size percentage shared by UI and text surfaces. */
  fontSizePercent?: number
  /** Optional primary UI color applied to action and selection surfaces. */
  themePrimaryColor?: string
  /** Optional soft UI color applied to muted primary backgrounds. */
  themeSoftColor?: string
  /** Maximum number of nodes to return in the knowledge graph. */
  graphNodeLimit?: number
  /** Whether to show the floating Agent window when the desktop shell starts. */
  floatingLaunchEnabled?: boolean
  /** Relative directory used when Markdown Edit mode saves pasted clipboard images. */
  editorImageAssetsDir?: string
  /** Legacy single-value localStorage field, normalized into uiFontFamilies. */
  uiFontFamily?: string
  /** Legacy single-value localStorage field, normalized into textFontFamilies. */
  textFontFamily?: string
}

/** Backend knowledge library config shown in settings/profile responses. */
export interface KnowledgeLibraryProfile {
  /** Stable library id derived from user and normalized directory. */
  libraryId: string
  /** Display name for the knowledge library. */
  name: string
  /** Absolute local knowledge root path. */
  knowledgeDir: string
  /** Relative storage directory for files created by the virtual library page. */
  libraryStorageDir: string
  /** Whether this library is the current active root. */
  isActive: boolean
}
