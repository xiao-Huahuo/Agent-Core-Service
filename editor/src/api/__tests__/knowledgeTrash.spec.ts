/** Knowledge-trash restore API request and derivative-state response tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { restoreKnowledgeTrashEntry } from '@/api/knowledge'

describe('knowledge trash API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('restores a trash entry and returns managed artifact rebuild status', async () => {
    const payload = {
      ok: true,
      restored_path: 'notes/demo.md',
      node: { name: 'demo.md', path: 'notes/demo.md', isDir: false },
      artifacts_restored: true,
      files_reingested: 1,
      graphs_restored: 1,
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json(payload))
    vi.stubGlobal('fetch', fetchMock)

    const result = await restoreKnowledgeTrashEntry('user/1', 'trash/1')

    expect(fetchMock).toHaveBeenCalledWith(
      '/knowledge/files/trash/trash%2F1/restore',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ user_id: 'user/1' }) }),
    )
    expect(result).toEqual(payload)
  })
})
