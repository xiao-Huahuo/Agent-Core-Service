/*
 * Settings DTOs for the editor front-end.
 *
 * Usage:
 * These types mirror the future persisted user settings endpoints while the
 * current front-end keeps data in localStorage.
 */

/** Theme mode applied to documentElement. */
export type ThemeMode = 'dark' | 'light' | 'system'

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
}

/** Backend knowledge library config shown in settings/profile responses. */
export interface KnowledgeLibraryProfile {
  /** Stable library id derived from user and normalized directory. */
  libraryId: string
  /** Display name for the knowledge library. */
  name: string
  /** Absolute local knowledge root path. */
  knowledgeDir: string
  /** Whether this library is the current active root. */
  isActive: boolean
}
