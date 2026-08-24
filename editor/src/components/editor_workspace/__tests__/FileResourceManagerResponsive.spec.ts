/**
 * File resource-manager responsive structure regression tests.
 *
 * Usage:
 * Guards the semantic toolbar and row hooks required for three container-width
 * layouts when the workspace is squeezed by the draggable browser sidebar.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import resourceManagerSource from '../FileResourceManager.vue?raw'

const resourceManagerCss = readFileSync(resolve(__dirname, '../FileResourceManager.css'), 'utf8')

describe('FileResourceManager responsive structure', () => {
  it('uses its own inline size for tablet and mobile layout changes', () => {
    expect(resourceManagerCss).toContain('container-type: inline-size')
    expect(resourceManagerCss).toContain('@container (max-width: 1040px)')
    expect(resourceManagerCss).toContain('@container (max-width: 640px)')
  })

  it('provides semantic toolbar groups and responsive file columns', () => {
    expect(resourceManagerSource).toContain('class="toolbar-primary"')
    expect(resourceManagerSource).toContain('class="toolbar-actions"')
    expect(resourceManagerSource).toContain('class="column-name name-cell"')
    expect(resourceManagerSource).toContain('class="column-modified"')
    expect(resourceManagerSource).toContain('class="column-ingested"')
    expect(resourceManagerSource).toContain('class="column-type"')
    expect(resourceManagerSource).toContain('class="column-size"')
  })
})
