/*
 * Agent streaming API reference transport tests.
 *
 * Verifies that quoted text is sent in a JSON body instead of a length-limited URL.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchAgentAttachment, streamPrompt, updateCurrentDocumentContext, uploadAgentAttachment } from '../agent'

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

  it('posts the current user bubble attachments in the streaming request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('data: [DONE]\n\n', {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const attachment = {
      attachment_id: 'att-1', user_id: 'user-1', session_id: 'session-1',
      library_id: 'default', library_name: '默认知识库', filename: '报告.pdf', stored_name: '报告.pdf',
      uri: 'session-upload://user-1/default/session-1/报告.pdf', mime_type: 'application/pdf',
      size: 42, source_type: 'document', created_at: '2026-08-30T08:00:00Z',
    }

    const stream = streamPrompt('user-1', 'session-1', '分析附件', { attachments: [attachment] })
    await stream.next()

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(init.body)).attachments).toEqual([attachment])
  })

  it('reports the current multi-file selection to Agent context', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await updateCurrentDocumentContext({
      user_id: 'user-1',
      path: 'docs/a.pdf',
      name: 'a.pdf',
      knowledge_dir: 'D:/knowledge',
      library_id: 'library-1',
      library_name: 'Knowledge',
      dirty: false,
      open_tab_count: 1,
      selected_paths: ['docs/a.pdf', 'docs/b.docx'],
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(init.body)).selected_paths).toEqual(['docs/a.pdf', 'docs/b.docx'])
  })

  it('fetches one attachment processing state with user and session ownership', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, attachment: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchAgentAttachment('user/1', 'session 1', 'att-1')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/agent/attachments/att-1?user_id=user%2F1&session_id=session+1')
  })

  it('reports native upload progress without blocking on attachment parsing', async () => {
    const progress: number[] = []

    class FakeRequest {
      upload: { onprogress?: (event: ProgressEvent) => void } = {}
      timeout = 0
      status = 200
      responseText = JSON.stringify({ ok: true, attachment: { attachment_id: 'att-1' } })
      onerror?: () => void
      ontimeout?: () => void
      onload?: () => void
      open() { /* request construction is covered by the response assertion */ }
      send() {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 } as ProgressEvent)
        this.onload?.()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeRequest)

    const response = await uploadAgentAttachment('u1', 's1', new File(['image'], 'image.png'), (value) => progress.push(value))

    expect(progress).toEqual([50])
    expect(response.attachment.attachment_id).toBe('att-1')
  })
})
