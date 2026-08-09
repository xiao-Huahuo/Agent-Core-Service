/*
 * Submenu intent geometry tests.
 *
 * Usage:
 * Verifies the invisible triangle used to keep nested context menus open
 * while the pointer travels toward a submenu.
 */
import { describe, expect, it } from 'vitest'

import { pointInTriangle } from '../submenuIntent'

describe('submenu intent triangle', () => {
  it('detects pointer movement inside the submenu travel corridor', () => {
    const origin = { x: 100, y: 100 }
    const submenuTop = { x: 260, y: 60 }
    const submenuBottom = { x: 260, y: 180 }

    expect(pointInTriangle({ x: 180, y: 110 }, origin, submenuTop, submenuBottom)).toBe(true)
    expect(pointInTriangle({ x: 180, y: 220 }, origin, submenuTop, submenuBottom)).toBe(false)
  })
})
