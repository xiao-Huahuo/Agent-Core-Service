/*
 * Git sidebar interaction structure tests.
 *
 * Usage:
 * Protects the IDE-style bottom commit footer, branch switcher, indented file
 * rows, anchored history dropdown, and creatable push targets requested by the
 * editor UI.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const componentRoot = resolve(__dirname, '..')
const sidebarSource = readFileSync(resolve(componentRoot, 'GitSidebar.vue'), 'utf-8')
const groupSource = readFileSync(resolve(componentRoot, 'GitChangeGroup.vue'), 'utf-8')
const pushSource = readFileSync(resolve(componentRoot, 'GitPushDialog.vue'), 'utf-8')

describe('Git sidebar interaction structure', () => {
  it('keeps the commit panel in the sidebar bottom row with an anchored history dropdown', () => {
    expect(sidebarSource).toContain('GitHistoryDropdown')
    expect(sidebarSource).not.toContain('GitHistoryDialog')
    expect(sidebarSource).toMatch(/\.git-sidebar\s*\{[^}]*display:\s*flex/s)
    expect(sidebarSource).toMatch(/\.git-sidebar\s*\{[^}]*overflow:\s*hidden/s)
    expect(sidebarSource).toMatch(/\.git-ready\s*\{[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\) auto/s)
    expect(sidebarSource).toMatch(/\.git-groups\s*\{[^}]*overflow:\s*auto/s)
    expect(sidebarSource).not.toMatch(/\.commit-panel\s*\{[^}]*position:\s*sticky/s)
  })

  it('shows a local branch switcher beside the history control', () => {
    expect(sidebarSource).toContain('class="commit-toolbar"')
    expect(sidebarSource).toContain('class="branch-switcher"')
    expect(sidebarSource).toContain('gitStore.switchBranch')
    expect(sidebarSource).toContain('gitStore.status.branches')
  })

  it('indents the complete file row beneath its change group', () => {
    expect(groupSource).toMatch(/\.change-row\s*\{[^}]*padding-left:\s*var\(--space-24\)/s)
  })

  it('opens explicit creation dialogs from all three dropdowns', () => {
    expect(pushSource).toContain('GitPushTargetCreateDialog')
    expect(pushSource).toContain('CREATE_LOCAL_VALUE')
    expect(pushSource).toContain('CREATE_REMOTE_VALUE')
    expect(pushSource).toContain('CREATE_REMOTE_BRANCH_VALUE')
    expect(pushSource).not.toContain('datalist')
  })

  it('locks the dialog frame and scrolls only the two preview lists', () => {
    expect(pushSource).toMatch(/\.push-dialog\s*\{[^}]*overflow:\s*hidden/s)
    expect(pushSource).toMatch(/\.push-dialog\s*\{[^}]*border-radius:\s*var\(--radius-xl\)/s)
    expect(pushSource).toMatch(/\.push-dialog\s*\{[^}]*font-family:\s*var\(--font-ui\)/s)
    expect(pushSource.match(/class="scroll-region"/g)).toHaveLength(2)
  })
})
