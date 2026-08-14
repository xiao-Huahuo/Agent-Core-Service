/**
 * File resource-manager menu integration tests.
 *
 * Usage:
 * Guards the toolbar sort menu and the workspace context menu against falling
 * back to local, visually inconsistent menu implementations.
 */
import { describe, expect, it } from 'vitest'

import resourceManagerSource from '../FileResourceManager.vue?raw'

describe('FileResourceManager menu integration', () => {
  it('uses the shared dropdown primitives for sorting', () => {
    expect(resourceManagerSource).toContain('<DropdownMenu v-if="resourcePage === \'files\'"')
    expect(resourceManagerSource).toContain('<DropdownMenuRadioGroup v-model="sortKey">')
    expect(resourceManagerSource).toContain('<DropdownMenuRadioGroup v-model="sortDirection">')
    expect(resourceManagerSource).not.toContain('class="sort-menu"')
  })

  it('keeps the shared context menu wired to the resource manager', () => {
    expect(resourceManagerSource).toContain('<FileContextMenu')
  })
})
