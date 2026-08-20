/**
 * Editor workspace shell style regression tests.
 *
 * Usage:
 * Guards the main workspace card against reintroducing the removed raised
 * shadow treatment.
 */
import { describe, expect, it } from 'vitest'

import editorWorkspaceSource from '@/views/EditorWorkspace.vue?raw'

describe('EditorWorkspace shell styling', () => {
  it('renders the main card without the raised shadow', () => {
    expect(editorWorkspaceSource).not.toContain('--workspace-card-shadow-dark')
    expect(editorWorkspaceSource).not.toContain('15px 15px 30px')
  })

  it('keeps the editor sidebar structurally independent from the Agent sidebar', () => {
    expect(editorWorkspaceSource).toContain('<aside class="editor-sidebar-content"')
    expect(editorWorkspaceSource).toContain('<EditorPane v-if="editorSidebarVisible" sidebar')
    expect(editorWorkspaceSource).toContain('class="agent-col"')
  })
})
