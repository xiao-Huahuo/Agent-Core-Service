/** Agent task queue API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueueTask, fetchQueue, transitionQueueTask } from '@/api/agentQueue'

describe('Agent queue API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists one user queue with the requested history scope', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ tasks: [], settings: { max_concurrency: 5 } }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchQueue('user/1', true)

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/agent-queue/tasks?user_id=user%2F1&history=true')
  })

  it('creates a task with its already isolated upload session', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await createQueueTask({ user_id: 'u1', prompt: '整理资料', priority: 'medium', attachments: [], session_id: 'sess_1' })

    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/agent-queue/tasks')
    expect(JSON.parse(String(request.body))).toMatchObject({ user_id: 'u1', session_id: 'sess_1' })
  })

  it('sends termination through the guarded state transition endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await transitionQueueTask('task/a', 'u1', 'terminated')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/agent-queue/tasks/task%2Fa/transition')
  })
})
