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
import { ensureSettingsProfile, fetchWebSearchConfig, rebuildKnowledgeRoot, saveAppearanceConfig, saveFontConfig, saveGraphConfig, saveKnowledgeIngestionConfig, saveWebSearchConfig, updateSettingsKnowledgeDir } from '@/api/settings'
import type { AgentAccessMode, AgentLoopMode } from '@/api/agent'
import type { SettingsKnowledgeLibraryResponse, SettingsProfileResponse } from '@/api/settings'
import type { KnowledgeLibraryProfile } from '@/types/settings'
import type { SidebarDisplayMode, ThemeMode, UserSettingsProfile } from '@/types/settings'

const THEME_KEY = 'agent_editor_theme_mode'
const PROFILE_KEY = 'agent_editor_profile'
const CHAT_MODE_KEY = 'agent_editor_chat_mode'
const AGENT_LOOP_MODE_KEY = 'agent_editor_loop_mode'
const AGENT_ACCESS_MODE_KEY = 'agent_editor_access_mode'
const SHOW_INDEX_COLUMN_KEY = 'agent_editor_show_index_column'
const SHOW_GRAPH_COLUMN_KEY = 'agent_editor_show_graph_column'
const SHOW_FAVORITE_COLUMN_KEY = 'agent_editor_show_favorite_column'
const SIDEBAR_DISPLAY_MODE_KEY = 'agent_editor_sidebar_display_mode'
const FLOATING_ENABLED_KEY = 'agent_editor_floating_enabled'
const FLOATING_PIN_MODE_KEY = 'agent_editor_floating_pin_mode'

const DEFAULT_UI_FONT_STACK = 'var(--font-ui-default)'
const DEFAULT_TEXT_FONT_STACK = 'var(--font-text-default)'
const DEFAULT_THEME_PRIMARY_COLOR = '#4224eb'
const DEFAULT_THEME_SOFT_COLOR = '#4224eb'
const APPEARANCE_PREVIEW_EVENT = 'metaweave:appearance-preview'

const DEFAULT_PROFILE: UserSettingsProfile = {
  userId: '',
  knowledgeDir: 'D:/Knowledge',
  activeLibraryId: '',
  knowledgeLibraries: [],
  knowledgeWatchEnabled: true,
  proxyUrl: '',
  webSearchEnabled: false,
  webSearchMaxResults: 10,
  autoIngestOnUpload: false,
  ocrEnabled: false,
  knowledgeIgnorePatterns: '',
  uiFontFamilies: [],
  textFontFamilies: [],
  fontSizePercent: 100,
  themePrimaryColor: '',
  themeSoftColor: '',
  graphNodeLimit: 2000,
}

function normalizeThemeColor(value: string | undefined): string {
  const color = (value ?? '').trim()
  if (!color) return ''
  if (/^#[0-9a-fA-F]{3}$/u.test(color)) {
    return `#${color.slice(1).split('').map((item) => item + item).join('')}`.toLowerCase()
  }
  if (/^#[0-9a-fA-F]{6}$/u.test(color)) {
    return color.toLowerCase()
  }
  return ''
}

function hexToRgb(value: string): { r: number; g: number; b: number } {
  const color = normalizeThemeColor(value) || DEFAULT_THEME_PRIMARY_COLOR
  return {
    r: Number.parseInt(color.slice(1, 3), 16),
    g: Number.parseInt(color.slice(3, 5), 16),
    b: Number.parseInt(color.slice(5, 7), 16),
  }
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((item) => Math.round(Math.max(0, Math.min(255, item))).toString(16).padStart(2, '0')).join('')}`
}

function mixWithWhite(value: string, amount: number): string {
  const color = hexToRgb(value)
  return rgbToHex(
    color.r + (255 - color.r) * amount,
    color.g + (255 - color.g) * amount,
    color.b + (255 - color.b) * amount,
  )
}

function rgbaFromHex(value: string, alpha: number): string {
  const color = hexToRgb(value)
  return `rgba(${color.r}, ${color.g}, ${color.b}, ${alpha})`
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

function normalizeFontSizePercent(value: number | string | undefined): number {
  const parsed = Number(value ?? 100)
  if (!Number.isFinite(parsed)) return 100
  return Math.max(50, Math.min(150, Math.round(parsed)))
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
    fontSizePercent: normalizeFontSizePercent(profile.fontSizePercent),
    themePrimaryColor: normalizeThemeColor(profile.themePrimaryColor),
    themeSoftColor: normalizeThemeColor(profile.themeSoftColor),
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
    libraryStorageDir: library.library_storage_dir ?? 'library',
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
    fontSizePercent: normalizeFontSizePercent(profileResponse.font_size_percent),
    themePrimaryColor: profileResponse.theme_primary_color ?? '',
    themeSoftColor: profileResponse.theme_soft_color ?? '',
    graphNodeLimit: profileResponse.graph_node_limit ?? 2000,
  }
}

function mapBackendWebSearchConfig(config: { proxy_url: string; web_search_enabled: boolean; web_search_max_results?: number }): Partial<UserSettingsProfile> {
  return {
    proxyUrl: config.proxy_url,
    webSearchEnabled: config.web_search_enabled,
    webSearchMaxResults: config.web_search_max_results ?? 10,
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

function normalizeAgentAccessMode(mode: string | null): AgentAccessMode {
  if (mode === 'readonly' || mode === 'full_access') {
    return mode
  }
  return 'sandbox'
}

function normalizeSidebarDisplayMode(mode: string | null): SidebarDisplayMode {
  return mode === 'management' ? 'management' : 'icons'
}

function normalizeFloatingPinMode(mode: string | null): 'off' | 'normal' | 'global' {
  return mode === 'off' || mode === 'global' ? mode : 'normal'
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
  const chatMode = ref<'chat' | 'tool'>((localStorage.getItem(CHAT_MODE_KEY) as 'chat' | 'tool' | null) ?? 'tool')

  /** Agent execution loop mode shared by Agent panel and Obs graph. */
  const agentLoopMode = ref<AgentLoopMode>(normalizeAgentLoopMode(localStorage.getItem(AGENT_LOOP_MODE_KEY)))

  /** Agent filesystem and terminal permission mode for the next turn. */
  const agentAccessMode = ref<AgentAccessMode>(normalizeAgentAccessMode(localStorage.getItem(AGENT_ACCESS_MODE_KEY)))

  /** Whether to show index status column/icons in file tree and file resource manager. */
  const showIndexColumn = ref(localStorage.getItem(SHOW_INDEX_COLUMN_KEY) !== 'false')

  /** Whether to show semantic graph status column/icons in file tree and file resource manager. */
  const showGraphColumn = ref(localStorage.getItem(SHOW_GRAPH_COLUMN_KEY) !== 'false')

  /** Whether to show favorite status buttons in the file tree. */
  const showFavoriteColumn = ref(localStorage.getItem(SHOW_FAVORITE_COLUMN_KEY) !== 'false')

  /** Left workspace sidebar mode: icon-only rail or wider management rail. */
  const sidebarDisplayMode = ref<SidebarDisplayMode>(normalizeSidebarDisplayMode(localStorage.getItem(SIDEBAR_DISPLAY_MODE_KEY)))

  /** Whether the floating Agent window is available from tray / settings. */
  const floatingEnabled = ref(localStorage.getItem(FLOATING_ENABLED_KEY) !== 'false')

  /** Floating Agent window pin mode: off / normal (above normal apps) / global (above all). */
  const floatingPinMode = ref<'off' | 'normal' | 'global'>(normalizeFloatingPinMode(localStorage.getItem(FLOATING_PIN_MODE_KEY)))

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
    window.dispatchEvent(new CustomEvent(APPEARANCE_PREVIEW_EVENT))
  }

  function applyFonts() {
    document.documentElement.style.setProperty(
      '--font-scale',
      String(normalizeFontSizePercent(profile.value.fontSizePercent) / 100),
    )
    document.documentElement.style.setProperty(
      '--font-ui',
      buildFontStack(profile.value.uiFontFamilies, DEFAULT_UI_FONT_STACK),
    )
    document.documentElement.style.setProperty(
      '--font-text',
      buildFontStack(profile.value.textFontFamilies, DEFAULT_TEXT_FONT_STACK),
    )
  }

  function applyAppearanceColorValues(themePrimaryColor?: string, themeSoftColor?: string) {
    const rootStyle = document.documentElement.style
    const primaryColor = normalizeThemeColor(themePrimaryColor)
    const softColor = normalizeThemeColor(themeSoftColor)
    if (primaryColor) {
      rootStyle.setProperty('--color-primary', primaryColor)
      rootStyle.setProperty('--color-primary-hover', mixWithWhite(primaryColor, 0.12))
      rootStyle.setProperty('--color-selection-blue', primaryColor)
      rootStyle.setProperty('--color-blue', primaryColor)
    } else {
      rootStyle.removeProperty('--color-primary')
      rootStyle.removeProperty('--color-primary-hover')
      rootStyle.removeProperty('--color-selection-blue')
      rootStyle.removeProperty('--color-blue')
    }
    if (softColor) {
      rootStyle.setProperty('--color-primary-soft', rgbaFromHex(softColor, 0.16))
      rootStyle.setProperty('--color-primary-softer', rgbaFromHex(softColor, 0.1))
      rootStyle.setProperty('--color-selection-blue-soft', rgbaFromHex(softColor, 0.16))
      rootStyle.setProperty('--color-user-bubble', rgbaFromHex(softColor, 0.16))
      rootStyle.setProperty('--color-user-bubble-border', rgbaFromHex(softColor, 0.46))
      rootStyle.setProperty('--color-user-bubble-glow', rgbaFromHex(softColor, 0.18))
      rootStyle.setProperty('--color-agent-bubble', rgbaFromHex(softColor, 0.12))
      rootStyle.setProperty('--color-agent-bubble-border', rgbaFromHex(softColor, 0.38))
      rootStyle.setProperty('--color-agent-bubble-glow', rgbaFromHex(softColor, 0.14))
    } else {
      rootStyle.removeProperty('--color-primary-soft')
      rootStyle.removeProperty('--color-primary-softer')
      rootStyle.removeProperty('--color-selection-blue-soft')
      rootStyle.removeProperty('--color-user-bubble')
      rootStyle.removeProperty('--color-user-bubble-border')
      rootStyle.removeProperty('--color-user-bubble-glow')
      rootStyle.removeProperty('--color-agent-bubble')
      rootStyle.removeProperty('--color-agent-bubble-border')
      rootStyle.removeProperty('--color-agent-bubble-glow')
    }
  }

  function applyAppearanceColors() {
    applyAppearanceColorValues(profile.value.themePrimaryColor, profile.value.themeSoftColor)
    window.dispatchEvent(new CustomEvent(APPEARANCE_PREVIEW_EVENT))
  }

  function previewAppearanceColors(params: { themePrimaryColor?: string; themeSoftColor?: string }) {
    applyAppearanceColorValues(params.themePrimaryColor, params.themeSoftColor)
    window.dispatchEvent(new CustomEvent(APPEARANCE_PREVIEW_EVENT))
  }

  function persistProfile() {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile.value))
  }

  /** Restore persisted theme and attach system color-scheme listener. */
  function initTheme() {
    applyTheme()
    applyFonts()
    applyAppearanceColors()
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', applyTheme)
  }

  /** Set explicit theme mode and immediately apply CSS variables. */
  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    localStorage.setItem(THEME_KEY, mode)
    applyTheme()
    // Keep the floating Agent window's theme in sync.
    window.agentEditorDesktop?.windowSync?.('theme', mode)
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

  function setShowGraphColumn(value: boolean) {
    showGraphColumn.value = value
    localStorage.setItem(SHOW_GRAPH_COLUMN_KEY, String(value))
  }

  function setShowFavoriteColumn(value: boolean) {
    showFavoriteColumn.value = value
    localStorage.setItem(SHOW_FAVORITE_COLUMN_KEY, String(value))
  }

  function setSidebarDisplayMode(mode: SidebarDisplayMode) {
    sidebarDisplayMode.value = normalizeSidebarDisplayMode(mode)
    localStorage.setItem(SIDEBAR_DISPLAY_MODE_KEY, sidebarDisplayMode.value)
  }

  function setFloatingEnabled(value: boolean) {
    floatingEnabled.value = value
    localStorage.setItem(FLOATING_ENABLED_KEY, String(value))
  }

  function setFloatingPinMode(mode: 'off' | 'normal' | 'global') {
    floatingPinMode.value = normalizeFloatingPinMode(mode)
    localStorage.setItem(FLOATING_PIN_MODE_KEY, floatingPinMode.value)
  }

  function setAgentLoopMode(mode: AgentLoopMode) {
    agentLoopMode.value = mode
    localStorage.setItem(AGENT_LOOP_MODE_KEY, mode)
  }

  function setAgentAccessMode(mode: AgentAccessMode) {
    agentAccessMode.value = normalizeAgentAccessMode(mode)
    localStorage.setItem(AGENT_ACCESS_MODE_KEY, agentAccessMode.value)
  }

  /** Update local profile values until backend settings are connected. */
  function updateProfile(nextProfile: Partial<UserSettingsProfile>) {
    profile.value = normalizeProfile({ ...profile.value, ...nextProfile })
    persistProfile()
    applyFonts()
    applyAppearanceColors()
  }

  function setUiFontFamilies(fontFamilies: string[]) {
    updateProfile({ uiFontFamilies: fontFamilies })
  }

  function setTextFontFamilies(fontFamilies: string[]) {
    updateProfile({ textFontFamilies: fontFamilies })
  }

  function setFontSizePercent(value: number) {
    updateProfile({ fontSizePercent: normalizeFontSizePercent(value) })
  }

  async function saveFontSettings(
    params: { uiFontFamilies?: string[]; textFontFamilies?: string[]; fontSizePercent?: number },
  ) {
    const nextUiFontFamilies = params.uiFontFamilies ?? profile.value.uiFontFamilies
    const nextTextFontFamilies = params.textFontFamilies ?? profile.value.textFontFamilies
    const nextFontSizePercent = normalizeFontSizePercent(params.fontSizePercent ?? profile.value.fontSizePercent)
    updateProfile({
      uiFontFamilies: nextUiFontFamilies,
      textFontFamilies: nextTextFontFamilies,
      fontSizePercent: nextFontSizePercent,
    })
    if (!hasUserId.value) {
      return null
    }
    try {
      const result = await saveFontConfig(profile.value.userId, {
        uiFontFamilies: nextUiFontFamilies,
        textFontFamilies: nextTextFontFamilies,
        fontSizePercent: nextFontSizePercent,
      })
      updateProfile({
        uiFontFamilies: result.ui_font_families,
        textFontFamilies: result.text_font_families,
        fontSizePercent: result.font_size_percent,
      })
      return result
    } catch (error) {
      if (error instanceof ApiError && error.status === 405) {
        throw new Error('保存字体设置失败: 后端尚未加载字体配置接口,请重启后端服务')
      }
      throw new Error('保存字体设置失败')
    }
  }

  async function saveAppearanceSettings(params: { themePrimaryColor?: string; themeSoftColor?: string }) {
    const nextThemePrimaryColor = normalizeThemeColor(params.themePrimaryColor ?? profile.value.themePrimaryColor)
    const nextThemeSoftColor = normalizeThemeColor(params.themeSoftColor ?? profile.value.themeSoftColor)
    updateProfile({
      themePrimaryColor: nextThemePrimaryColor,
      themeSoftColor: nextThemeSoftColor,
    })
    if (!hasUserId.value) {
      return null
    }
    try {
      const result = await saveAppearanceConfig(profile.value.userId, {
        themePrimaryColor: nextThemePrimaryColor,
        themeSoftColor: nextThemeSoftColor,
      })
      updateProfile({
        themePrimaryColor: result.theme_primary_color,
        themeSoftColor: result.theme_soft_color,
      })
      return result
    } catch (error) {
      if (error instanceof ApiError && error.status === 405) {
        throw new Error('保存外观设置失败: 后端尚未加载外观配置接口,请重启后端服务')
      }
      throw new Error('保存外观设置失败')
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

  async function saveGraphSettings(params: { graphNodeLimit?: number }) {
    if (!hasUserId.value) {
      updateProfile({
        graphNodeLimit: params.graphNodeLimit ?? profile.value.graphNodeLimit,
      })
      return
    }
    const prev = { graphNodeLimit: profile.value.graphNodeLimit }
    updateProfile({
      graphNodeLimit: params.graphNodeLimit ?? profile.value.graphNodeLimit,
    })
    try {
      const result = await saveGraphConfig(profile.value.userId, params)
      updateProfile({ graphNodeLimit: result.graph_node_limit })
      return result
    } catch {
      updateProfile(prev)
      throw new Error('保存图谱设置失败')
    }
  }

  return {
    themeMode,
    colorScheme,
    chatMode,
    agentLoopMode,
    agentAccessMode,
    sidebarDisplayMode,
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
    setAgentAccessMode,
    setSidebarDisplayMode,
    floatingEnabled,
    setFloatingEnabled,
    floatingPinMode,
    setFloatingPinMode,
    updateProfile,
    setUiFontFamilies,
    setTextFontFamilies,
    setFontSizePercent,
    saveFontSettings,
    previewAppearanceColors,
    saveAppearanceSettings,
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
    saveGraphSettings,
    setAutoIngestOnUpload,
    showIndexColumn,
    setShowIndexColumn,
    showGraphColumn,
    setShowGraphColumn,
    showFavoriteColumn,
    setShowFavoriteColumn,
  }
})
