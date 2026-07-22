/*
 * Agent streaming API reference transport tests.
 *
 * Verifies that quoted text is sent in a JSON body instead of a length-limited URL.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamPrompt } from '../agent'

describe('streamPrompt reference transport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the reference in the streaming request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('data: [DONE]\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const stream = streamPrompt('user-1', 'session-1', '请解释', {
      reference: '被引用的文档内容',
    })
    await stream.next()

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).not.toContain('reference=')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      user_id: 'user-1',
      session_id: 'session-1',
      prompt: '请解释',
      reference: '被引用的文档内容',
      agent_mode: 'auto',
      agent_access_mode: 'sandbox',
    })
  })
})
