/** Literature-reading API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { deleteLiteratureRow, listLiteratureEntries, patchLiteratureRow } from '@/api/literatureReading'

describe('literature reading API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists rows within the active knowledge library', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json([]))
    vi.stubGlobal('fetch', fetchMock)

    await listLiteratureEntries('user/1', 'library/a')

    expect(fetchMock).toHaveBeenCalledWith(
      '/literature-reading/entries?user_id=user%2F1&library_id=library%2Fa',
      expect.any(Object),
    )
  })

  it('patches encoded row ids without replacing the whole form', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ form: {} }))
    vi.stubGlobal('fetch', fetchMock)

    await patchLiteratureRow('u1', 'form/a', 'row/1', { title: { value: '新标题' } })

    expect(fetchMock).toHaveBeenCalledWith(
      '/literature-reading/form%2Fa/rows/row%2F1',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ user_id: 'u1', cells: { title: { value: '新标题' } } }) }),
    )
  })

  it('deletes the row and its real file explicitly', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteLiteratureRow('u1', 'f1', 'r1', true)

    expect(fetchMock).toHaveBeenCalledWith(
      '/literature-reading/f1/rows/r1?user_id=u1&delete_file=true',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
