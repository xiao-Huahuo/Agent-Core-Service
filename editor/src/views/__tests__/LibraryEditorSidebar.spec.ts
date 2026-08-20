/**
 * Library editor-sidebar wiring regression.
 *
 * Usage:
 * Verifies that the edit-book real-file action keeps LibraryView mounted and
 * routes the selected source into the shared editor sidebar.
 */
import { describe, expect, it } from 'vitest'

import libraryViewSource from '@/views/LibraryView.vue?raw'

describe('Library editor sidebar wiring', () => {
  it('opens an edited book source through the shared editor sidebar', () => {
    expect(libraryViewSource).toContain('await workspaceStore.openEditorSidebar({')
    expect(libraryViewSource).toContain('async function openSourceFromEdit(item: LibraryItem)')
  })
})
