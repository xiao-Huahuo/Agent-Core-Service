/*
 * Top command bar knowledge-library entry tests.
 *
 * Usage:
 * Verifies that the active knowledge root path is exposed as hover metadata
 * without being rendered as left-side toolbar text.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import TopCommandBar from '../TopCommandBar.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

vi.mock('@/api/settings', () => ({
  checkModelDisk: vi.fn().mockResolvedValue({ embedding: 'downloaded' }),
}))

function prepareStores() {
  setActivePinia(createPinia())
  const settingsStore = useSettingsStore()
  const workspaceStore = useWorkspaceStore()
  settingsStore.updateProfile({
    userId: 'user-1',
    knowledgeDir: 'D:/Knowledge/Primary',
    activeLibraryId: 'library-1',
    knowledgeLibraries: [
      {
        libraryId: 'library-1',
        name: '主知识库',
        knowledgeDir: 'D:/Knowledge/Primary',
        libraryStorageDir: 'library',
        isActive: true,
      },
    ],
  })
  vi.spyOn(settingsStore, 'switchKnowledgeRoot').mockResolvedValue(null)
  vi.spyOn(workspaceStore, 'loadKnowledgeTree').mockResolvedValue()
  vi.spyOn(workspaceStore, 'restartFileWatcher').mockImplementation(() => {})
  return { settingsStore, workspaceStore }
}

function mountTopCommandBar() {
  return mount(TopCommandBar, {
    props: { gitOpen: false, browserOpen: false },
    global: {
      stubs: {
        SearchPalette: true,
        Teleport: true,
        Transition: false,
      },
    },
  })
}

describe('TopCommandBar knowledge-library switcher', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    Object.defineProperty(window, 'agentEditorDesktop', {
      configurable: true,
      value: {
        selectDirectory: vi.fn().mockResolvedValue('D:/Knowledge/Next'),
      },
    })
  })

  it('shows a folder button before the library name without rendering the root path as text', () => {
    prepareStores()
    const wrapper = mountTopCommandBar()

    const brandCopy = wrapper.get('.brand-copy')
    const folderButton = wrapper.get('button.library-folder-btn')

    expect(brandCopy.text()).toBe('')
    expect(folderButton.attributes('title')).toBe('D:/Knowledge/Primary')
    expect(folderButton.attributes('aria-label')).toBe('切换知识库')
    expect(wrapper.get('input.library-name-input').element).toHaveProperty('value', '主知识库')
  })

  it('keeps the toolbar search inside the right-side action group', () => {
    prepareStores()
    const wrapper = mountTopCommandBar()

    expect(wrapper.find('.topbar > .search-center').exists()).toBe(false)
    expect(wrapper.findAll('.actions > .search-center')).toHaveLength(1)
  })

  it('does not shrink the library name when an ingestion progress bar is visible', () => {
    const source = readFileSync(resolve(__dirname, '..', 'TopCommandBar.vue'), 'utf-8')

    expect(source).toMatch(/\.brand-copy\s*\{[^}]*flex:\s*0 0 auto;/su)
  })

  it('exposes the compact browser-sidebar toggle in the application top bar', async () => {
    prepareStores()
    const wrapper = mountTopCommandBar()

    await wrapper.get('button[aria-label="打开或收起右侧浏览器"]').trigger('click')

    expect(wrapper.emitted('toggleBrowser')).toHaveLength(1)
  })

  it('releases the collapsed search expansion area for window dragging', () => {
    const source = readFileSync(resolve(__dirname, '..', 'TopCommandBar.vue'), 'utf-8')

    expect(source).toMatch(/\.search-center\s*\{[^}]*flex:\s*0 0 26px;[^}]*width:\s*26px;/su)
    expect(source).toMatch(/\.search-center:has\(\.search-wrapper\.focused\)\s*\{[^}]*flex-basis:\s*250px;[^}]*width:\s*250px;/su)
  })

  it('reuses the existing directory picker flow when the folder button is clicked', async () => {
    const { settingsStore, workspaceStore } = prepareStores()
    const wrapper = mountTopCommandBar()

    await wrapper.get('button.library-folder-btn').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(window.agentEditorDesktop?.selectDirectory).toHaveBeenCalledOnce()
    expect(settingsStore.switchKnowledgeRoot).toHaveBeenCalledWith('D:/Knowledge/Next')
    expect(workspaceStore.loadKnowledgeTree).toHaveBeenCalledOnce()
    expect(workspaceStore.restartFileWatcher).toHaveBeenCalledOnce()
  })
})
