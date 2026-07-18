/*
 * Global settings store.
 *
 * Usage:
 * This is the only place that reads/writes theme and editor profile values.
 * Components call actions here instead of touching localStorage or DOM theme
 * attributes directly.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError } from '@/api/client'
import { ensureSettingsProfile, fetchWebSearchConfig, rebuildKnowledgeRoot, saveFontConfig, saveKnowledgeIngestionConfig, saveWebSearchConfig, updateSettingsKnowledgeDir } from '@/api/settings'
import type { AgentLoopMode } from '@/api/agent'
import type { SettingsKnowledgeLibraryResponse, SettingsProfileResponse } from '@/api/settings'
import type { KnowledgeLibraryProfile } from '@/types/settings'
import type { ThemeMode, UserSettingsProfile } from '@/types/settings'

const THEME_KEY = 'agent_editor_theme_mode'
const PROFILE_KEY = 'agent_editor_profile'
const CHAT_MODE_KEY = 'agent_editor_chat_mode'
const AGENT_LOOP_MODE_KEY = 'agent_editor_loop_mode'
const SHOW_INDEX_COLUMN_KEY = 'agent_editor_show_index_column'

const DEFAULT_UI_FONT_STACK = 'var(--font-ui-default)'
const DEFAULT_TEXT_FONT_STACK = 'var(--font-text-default)'

const DEFAULT_PROFILE: UserSettingsProfile = {
  userId: '',
  knowledgeDir: 'D:/Knowledge',
  activeLibraryId: '',
  knowledgeLibraries: [],
  knowledgeWatchEnabled: true,
  proxyUrl: '',
  webSearchEnabled: false,
  autoIngestOnUpload: false,
  ocrEnabled: false,
  knowledgeIgnorePatterns: '',
  uiFontFamilies: [],
  textFontFamilies: [],
}

function normalizeFontFamily(value: string | undefined): string {
  return (value ?? '').replace(/[;{}]/g, '').trim()
}

function normalizeFontFamilies(values: string[] | string | undefined): string[] {
  const sourceValues = Array.isArray(values) ? values : (values ? [values] : [])
  const seen = new Set<string>()
  const normalized: string[] = []
  for (const value of sourceValues) {
    const family = normalizeFontFamily(value)
    if (!family) continue
    const key = family.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    normalized.push(family)
  }
  return normalized
}

function quoteFontFamily(value: string): string {
  if (value.startsWith('var(') || /^[-_a-zA-Z][-_a-zA-Z0-9]*$/u.test(value)) {
    return value
  }
  return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
}

function buildFontStack(values: string[] | undefined, fallback: string): string {
  const normalized = normalizeFontFamilies(values)
  return normalized.length > 0
    ? `${normalized.map(quoteFontFamily).join(', ')}, ${fallback}`
    : fallback
}

function normalizeProfile(profile: UserSettingsProfile): UserSettingsProfile {
  const nextProfile = {
    ...DEFAULT_PROFILE,
    ...profile,
    userId: profile.userId.trim(),
    knowledgeLibraries: profile.knowledgeLibraries ?? [],
    uiFontFamilies: normalizeFontFamilies(profile.uiFontFamilies ?? profile.uiFontFamily),
    textFontFamilies: normalizeFontFamilies(profile.textFontFamilies ?? profile.textFontFamily),
  }
  if (nextProfile.userId === 'local-user') {
    nextProfile.userId = ''
  }
  return nextProfile
}

function mapKnowledgeLibrary(library: SettingsKnowledgeLibraryResponse): KnowledgeLibraryProfile {
  return {
    libraryId: library.library_id,
    name: library.name,
    knowledgeDir: library.knowledge_dir,
    isActive: library.is_active,
  }
}

function mapBackendProfile(profileResponse: SettingsProfileResponse): Partial<UserSettingsProfile> {
  return {
    userId: profileResponse.user_id,
    knowledgeDir: profileResponse.knowledge_dir,
    activeLibraryId: profileResponse.active_library_id ?? '',
    knowledgeLibraries: (profileResponse.knowledge_libraries ?? []).map(mapKnowledgeLibrary),
    autoIngestOnUpload: Boolean(profileResponse.auto_ingest_on_upload),
    ocrEnabled: Boolean(profileResponse.ocr_enabled),
    knowledgeIgnorePatterns: profileResponse.knowledge_ignore_patterns ?? '',
    uiFontFamilies: profileResponse.ui_font_families ?? [],
    textFontFamilies: profileResponse.text_font_families ?? [],
  }
}

function mapBackendWebSearchConfig(config: { proxy_url: string; web_search_enabled: boolean }): Partial<UserSettingsProfile> {
  return {
    proxyUrl: config.proxy_url,
    webSearchEnabled: config.web_search_enabled,
  }
}

function normalizeAgentLoopMode(mode: string | null): AgentLoopMode {
  if (mode === 'simple' || mode === 'react' || mode === 'plan') {
    return mode
  }
  if (mode === 'deep') {
    return 'plan'
  }
  return 'auto'
}

function loadProfile(): UserSettingsProfile {
  const raw = localStorage.getItem(PROFILE_KEY)
  if (!raw) {
    return normalizeProfile(DEFAULT_PROFILE)
  }
  try {
    return normalizeProfile({ ...DEFAULT_PROFILE, ...JSON.parse(raw) } as UserSettingsProfile)
  } catch {
    return normalizeProfile(DEFAULT_PROFILE)
  }
}

export const useSettingsStore = defineStore('settings', () => {
  /** Active theme mode persisted for the editor app. */
  const themeMode = ref<ThemeMode>((localStorage.getItem(THEME_KEY) as ThemeMode | null) ?? 'dark')

  /** Global color scheme token for CSS variable selection. */
  const colorScheme = ref('editor-default')

  /** User profile settings shared by future backend settings endpoints. */
  const profile = ref<UserSettingsProfile>(loadProfile())

  /** Chat bubble rendering mode shared by the editor Agent panel. */
  const chatMode = ref<'chat' | 'tool'>((localStorage.getItem(CHAT_MODE_KEY) as 'chat' | 'tool' | null) ?? 'chat')

  /** Agent execution loop mode shared by Agent panel and Obs graph. */
  const agentLoopMode = ref<AgentLoopMode>(normalizeAgentLoopMode(localStorage.getItem(AGENT_LOOP_MODE_KEY)))

  /** Whether to show index status column/icons in file tree and file resource manager. */
  const showIndexColumn = ref(localStorage.getItem(SHOW_INDEX_COLUMN_KEY) !== 'false')

  /** Whether the editor shell can enter workspace routes. */
  const hasUserId = computed(() => profile.value.userId.trim().length > 0)

  /** Active backend knowledge library config for the current root. */
  const activeKnowledgeLibrary = computed(() => {
    return profile.value.knowledgeLibraries.find((library) => library.libraryId === profile.value.activeLibraryId)
      ?? profile.value.knowledgeLibraries.find((library) => library.isActive)
      ?? null
  })

  const isDark = computed(() => {
    if (themeMode.value === 'system') {
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
    }
    return themeMode.value === 'dark'
  })

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    document.documentElement.setAttribute('data-color-scheme', colorScheme.value)
  }

  function applyFonts() {
    document.documentElement.style.setProperty(
      '--font-ui',
      buildFontStack(profile.value.uiFontFamilies, DEFAULT_UI_FONT_STACK),
    )
    document.documentElement.style.setProperty(
      '--font-text',
      buildFontStack(profile.value.textFontFamilies, DEFAULT_TEXT_FONT_STACK),
    )
  }

  function persistProfile() {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile.value))
  }

  /** Restore persisted theme and attach system color-scheme listener. */
  function initTheme() {
    applyTheme()
    applyFonts()
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', applyTheme)
  }

  /** Set explicit theme mode and immediately apply CSS variables. */
  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    localStorage.setItem(THEME_KEY, mode)
    applyTheme()
  }

  /** Toggle between dark and light for the toolbar button. */
  function toggleTheme() {
    setThemeMode(isDark.value ? 'light' : 'dark')
  }

  /** Toggle between compact chat bubbles and tool-node-aware rendering. */
  function toggleChatMode() {
    chatMode.value = chatMode.value === 'chat' ? 'tool' : 'chat'
    localStorage.setItem(CHAT_MODE_KEY, chatMode.value)
  }

  function setShowIndexColumn(value: boolean) {
    showIndexColumn.value = value
    localStorage.setItem(SHOW_INDEX_COLUMN_KEY, String(value))
  }

  function setAgentLoopMode(mode: AgentLoopMode) {
    agentLoopMode.value = mode
    localStorage.setItem(AGENT_LOOP_MODE_KEY, mode)
  }

  /** Update local profile values until backend settings are connected. */
  function updateProfile(nextProfile: Partial<UserSettingsProfile>) {
    profile.value = normalizeProfile({ ...profile.value, ...nextProfile })
    persistProfile()
    applyFonts()
  }

  function setUiFontFamilies(fontFamilies: string[]) {
    updateProfile({ uiFontFamilies: fontFamilies })
  }

  function setTextFontFamilies(fontFamilies: string[]) {
    updateProfile({ textFontFamilies: fontFamilies })
  }

  async function saveFontSettings(params: { uiFontFamilies?: string[]; textFontFamilies?: string[] }) {
    const nextUiFontFamilies = params.uiFontFamilies ?? profile.value.uiFontFamilies
    const nextTextFontFamilies = params.textFontFamilies ?? profile.value.textFontFamilies
    updateProfile({
      uiFontFamilies: nextUiFontFamilies,
      textFontFamilies: nextTextFontFamilies,
    })
    if (!hasUserId.value) {
      return null
    }
    try {
      const result = await saveFontConfig(profile.value.userId, {
        uiFontFamilies: nextUiFontFamilies,
        textFontFamilies: nextTextFontFamilies,
      })
      updateProfile({
        uiFontFamilies: result.ui_font_families,
        textFontFamilies: result.text_font_families,
      })
      return result
    } catch (error) {
      if (error instanceof ApiError && error.status === 405) {
        throw new Error('保存字体设置失败: 后端尚未加载字体配置接口,请重启后端服务')
      }
      throw new Error('保存字体设置失败')
    }
  }

  /** Replace local profile fields with a backend settings response. */
  function applyBackendProfile(profileResponse: SettingsProfileResponse) {
    updateProfile(mapBackendProfile(profileResponse))
  }

  /** Set the local user id required before entering the editor shell. */
  function setUserId(userId: string) {
    updateProfile({ userId })
  }

  /** Clear the local user id and return the app to the entry gate. */
  function clearUserId() {
    updateProfile({ userId: '' })
  }

  /** Refresh the cached user profile from the backend before entering the app. */
  async function refreshUserProfile() {
    if (!hasUserId.value) {
      return null
    }
    const nextProfile = await ensureSettingsProfile(profile.value.userId)
    applyBackendProfile(nextProfile)
    return nextProfile
  }

  /** Set the active local knowledge root path shown by the editor shell. */
  function setKnowledgeDir(knowledgeDir: string) {
    updateProfile({ knowledgeDir })
  }

  /** Persist and rebuild the active backend knowledge root. */
  async function switchKnowledgeRoot(knowledgeDir: string) {
    const normalizedDir = knowledgeDir.trim()
    if (!hasUserId.value || !normalizedDir) {
      return null
    }
    const nextProfile = await updateSettingsKnowledgeDir(profile.value.userId, normalizedDir)
    applyBackendProfile(nextProfile)
    const rebuildResult = await rebuildKnowledgeRoot(profile.value.userId)
    return rebuildResult
  }

  /** Persist a display name for the active backend knowledge library. */
  async function renameActiveKnowledgeLibrary(name: string) {
    const normalizedName = name.trim()
    if (!hasUserId.value || !profile.value.knowledgeDir || !normalizedName) {
      return null
    }
    const nextProfile = await updateSettingsKnowledgeDir(
      profile.value.userId,
      profile.value.knowledgeDir,
      normalizedName,
    )
    applyBackendProfile(nextProfile)
    return nextProfile
  }

  async function fetchWebSearchSettings() {
    if (!hasUserId.value) return
    try {
      const result = await fetchWebSearchConfig(profile.value.userId)
      updateProfile(mapBackendWebSearchConfig(result))
    } catch { /* not critical */ }
  }

  async function toggleWebSearch(enabled: boolean) {
    if (!hasUserId.value) return
    const prev = { proxyUrl: profile.value.proxyUrl, webSearchEnabled: profile.value.webSearchEnabled }
    updateProfile({ webSearchEnabled: enabled })
    try {
      await saveWebSearchConfig(profile.value.userId, { webSearchEnabled: enabled })
    } catch {
      updateProfile(prev)
    }
  }

  async function saveKnowledgeIngestionSettings(params: { autoIngestOnUpload?: boolean; ocrEnabled?: boolean; knowledgeIgnorePatterns?: string }) {
    if (!hasUserId.value) {
      updateProfile({
        autoIngestOnUpload: params.autoIngestOnUpload ?? profile.value.autoIngestOnUpload,
        ocrEnabled: params.ocrEnabled ?? profile.value.ocrEnabled,
        knowledgeIgnorePatterns: params.knowledgeIgnorePatterns ?? profile.value.knowledgeIgnorePatterns,
      })
      return
    }
    const prev = {
      autoIngestOnUpload: profile.value.autoIngestOnUpload,
      ocrEnabled: profile.value.ocrEnabled,
      knowledgeIgnorePatterns: profile.value.knowledgeIgnorePatterns,
    }
    updateProfile({
      autoIngestOnUpload: params.autoIngestOnUpload ?? profile.value.autoIngestOnUpload,
      ocrEnabled: params.ocrEnabled ?? profile.value.ocrEnabled,
      knowledgeIgnorePatterns: params.knowledgeIgnorePatterns ?? profile.value.knowledgeIgnorePatterns,
    })
    try {
      const result = await saveKnowledgeIngestionConfig(profile.value.userId, params)
      updateProfile({
        autoIngestOnUpload: result.auto_ingest_on_upload,
        ocrEnabled: result.ocr_enabled,
        knowledgeIgnorePatterns: result.knowledge_ignore_patterns,
      })
      return result
    } catch {
      updateProfile(prev)
      throw new Error('保存灌库设置失败')
    }
  }

  async function setAutoIngestOnUpload(enabled: boolean) {
    await saveKnowledgeIngestionSettings({ autoIngestOnUpload: enabled })
  }

  return {
    themeMode,
    colorScheme,
    chatMode,
    agentLoopMode,
    profile,
    hasUserId,
    activeKnowledgeLibrary,
    isDark,
    initTheme,
    applyFonts,
    setThemeMode,
    toggleTheme,
    toggleChatMode,
    setAgentLoopMode,
    updateProfile,
    setUiFontFamilies,
    setTextFontFamilies,
    saveFontSettings,
    applyBackendProfile,
    setUserId,
    clearUserId,
    refreshUserProfile,
    setKnowledgeDir,
    switchKnowledgeRoot,
    renameActiveKnowledgeLibrary,
    fetchWebSearchSettings,
    toggleWebSearch,
    saveKnowledgeIngestionSettings,
    setAutoIngestOnUpload,
    showIndexColumn,
    setShowIndexColumn,
  }
})
