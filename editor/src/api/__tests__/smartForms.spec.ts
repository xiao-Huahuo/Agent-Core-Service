/** Smart-form API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { deleteSmartFormDb } from '@/api/smartForms'

describe('smart forms API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('deletes the encoded table id for the current user', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteSmartFormDb('user/1', 'form/a')

    expect(fetchMock).toHaveBeenCalledWith(
      '/smart-forms/form%2Fa?user_id=user%2F1',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
