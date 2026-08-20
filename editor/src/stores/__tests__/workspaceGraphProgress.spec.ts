/**
 * Graph extraction aggregate-progress regression checks.
 *
 * Usage:
 * Verifies that the header progress includes the active document's internal
 * stage progress instead of advancing only when a whole document finishes.
 */
import { describe, expect, it } from 'vitest'

import { calculateGraphProgress } from '@/stores/workspace'

describe('workspace graph extraction progress', () => {
  it('includes completed, active, and pending document progress', () => {
    expect(calculateGraphProgress([
      { path: 'done.md', name: 'done', status: 'done', progress: 100 },
      { path: 'active.md', name: 'active', status: 'processing', progress: 50 },
      { path: 'pending.md', name: 'pending', status: 'pending', progress: 0 },
    ], 3)).toBe(50)
  })
})
