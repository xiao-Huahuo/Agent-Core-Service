/*
 * Agent SSE 请求构造回归测试。
 *
 * 用途：确保后台子 Agent 完成唤醒所需的消息元数据会提交给后端落库，
 * 历史恢复时不会退化成普通用户气泡。
 */
import { describe, expect, it, vi } from 'vitest'

import { streamPrompt } from '@/api/agent'

const mocks = vi.hoisted(() => ({
  streamLines: vi.fn(() => (async function* () {})()),
}))

vi.mock('@/api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/client')>(),
  buildApiUrl: (path: string) => path,
  streamLines: mocks.streamLines,
}))

describe('Agent stream API client', () => {
  it('posts child completion metadata for durable wakeup rendering', () => {
    const childAgentEvent = {
      event_name: 'child_agent.completed',
      child: { run_id: 'child-1', status: 'completed' },
    }

    streamPrompt('user-1', 'session-1', '继续主任务', {
      messageMetadata: { wakeup: true, child_agent_event: childAgentEvent },
    })

    const request = mocks.streamLines.mock.calls[0]?.[1] as RequestInit
    expect(JSON.parse(String(request.body))).toMatchObject({
      message_metadata: { wakeup: true, child_agent_event: childAgentEvent },
    })
  })
})
