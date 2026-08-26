/** Smart-table field icon and type-label regression tests. */

import { describe, expect, it } from 'vitest'

import {
  BUILTIN_COLUMN_ICONS,
  SMART_COLUMN_TYPE_ICONS,
  SMART_COLUMN_TYPE_LABELS,
} from '@/components/smart_forms/smartColumnPresentation'
import { BUILTIN_COLUMNS, createDefaultLiteratureForm } from '@/components/smart_forms/smartLiteratureTable'

describe('smartColumnPresentation', () => {
  it('assigns a distinct local icon to every required and optional built-in field', () => {
    const builtins = [...new Map(
      [...createDefaultLiteratureForm().columns, ...BUILTIN_COLUMNS].map((column) => [column.id, column]),
    ).values()]
    const icons = builtins.map((column) => BUILTIN_COLUMN_ICONS[column.id])

    expect(icons.every(Boolean)).toBe(true)
    expect(new Set(icons).size).toBe(builtins.length)
  })

  it('provides an icon and a visible label for every column type', () => {
    expect(Object.keys(SMART_COLUMN_TYPE_ICONS).sort()).toEqual(Object.keys(SMART_COLUMN_TYPE_LABELS).sort())
    expect(Object.values(SMART_COLUMN_TYPE_LABELS).every(Boolean)).toBe(true)
  })
})
