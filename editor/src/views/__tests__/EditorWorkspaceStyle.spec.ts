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

  it('routes editor and browser left-edge handles through the shared column resize flow', () => {
    expect(editorWorkspaceSource).toContain("type ResizeTarget = 'file' | 'editor' | 'browser' | 'agent'")
    expect(editorWorkspaceSource).toContain('aria-label="Resize editor sidebar"')
    expect(editorWorkspaceSource).toContain("@pointerdown=\"startResize('editor', $event)\"")
    expect(editorWorkspaceSource).toContain('aria-label="Resize browser sidebar"')
    expect(editorWorkspaceSource).toContain("@pointerdown=\"startResize('browser', $event)\"")
    expect(editorWorkspaceSource).toContain("'--editor-resizer-width'")
    expect(editorWorkspaceSource).toContain("'--browser-resizer-width'")
  })

  it('floats every right sidebar and keeps only the latest mobile overlay active', () => {
    expect(editorWorkspaceSource).toContain("type MobileSidebar = 'file' | 'editor' | 'browser' | 'git' | 'agent' | 'todo'")
    expect(editorWorkspaceSource).toContain('function activateMobileSidebar(sidebar: MobileSidebar): void')
    expect(editorWorkspaceSource).toContain("if (sidebar !== 'file')")
    expect(editorWorkspaceSource).toContain("if (sidebar !== 'browser') workspaceStore.closeBrowserSidebar()")
    expect(editorWorkspaceSource).toContain("if (sidebar !== 'agent') agentSidebarOpen.value = false")
    expect(editorWorkspaceSource).toMatch(
      /\.workspace-grid\.mobile-main-layout \.editor-sidebar-content,[\s\S]*?\.browser-sidebar-content,[\s\S]*?\.agent-col \{[\s\S]*?position: absolute;/,
    )
  })

  it('measures the mobile breakpoint independently from docked sidebar widths', () => {
    expect(editorWorkspaceSource).toContain('mainShellWidth.value = gridRect.width - activityBarWidth.value')
    expect(editorWorkspaceSource).not.toContain('shellRect.right - gridRect.left - activityBarWidth.value')
  })
})
