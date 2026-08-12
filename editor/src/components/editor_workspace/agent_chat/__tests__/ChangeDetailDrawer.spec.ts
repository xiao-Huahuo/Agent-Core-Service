/*
 * Change detail drawer tests.
 *
 * Usage:
 * Verifies local diff rows delegate complete snapshots to the shared renderer.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ChangeDetailDrawer from '../ChangeDetailDrawer.vue'

describe('ChangeDetailDrawer', () => {
  it('passes each saved edit to the shared diff renderer', () => {
    const wrapper = mount(ChangeDetailDrawer, {
      props: {
        snapshot: {
          snapshot_id: 'snap_1', session_id: 's1', run_id: 'run_1', created_at: '', additions: 1, deletions: 1, is_undone: false,
          files: [{ path: 'notes/a.md', additions: 1, deletions: 1, edits: [{ path: 'notes/a.md', before: 'keep\nold\ntail', after: 'keep\nnew\ntail', additions: 1, deletions: 1 }] }],
          edits: [],
        },
      },
    })

    const diff = wrapper.findComponent({ name: 'ChangeDiff' })
    expect(diff.props('before')).toBe('keep\nold\ntail')
    expect(diff.props('after')).toBe('keep\nnew\ntail')
  })
})
