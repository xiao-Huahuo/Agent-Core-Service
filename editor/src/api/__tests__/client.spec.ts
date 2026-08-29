/*
 * Shared streaming client scheduling tests.
 *
 * Verifies that a buffered SSE burst cannot monopolize the renderer task queue.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamLines } from '../client'

describe('streamLines scheduling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('yields to renderer tasks while consuming one buffered SSE burst', async () => {
    const events = Array.from({ length: 18 }, (_, index) => `data: {"index":${index}}\n\n`).join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(events, { status: 200 })))
    const order: string[] = []
    setTimeout(() => order.push('timer'), 0)

    for await (const event of streamLines('/agent/stream')) {
      order.push(String(event.index))
    }

    expect(order.indexOf('timer')).toBeGreaterThan(0)
    expect(order.indexOf('timer')).toBeLessThan(18)
    expect(order.filter((item) => item !== 'timer')).toEqual(Array.from({ length: 18 }, (_, index) => String(index)))
  })

  it('honors cancellation while a buffered SSE burst is yielding', async () => {
    const events = Array.from({ length: 18 }, (_, index) => `data: {"index":${index}}\n\n`).join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(events, { status: 200 })))
    const controller = new AbortController()
    const received: number[] = []
    setTimeout(() => controller.abort(), 0)

    for await (const event of streamLines('/agent/stream', { signal: controller.signal })) {
      received.push(Number(event.index))
    }

    expect(received.length).toBeGreaterThan(0)
    expect(received.length).toBeLessThan(18)
  })
})
