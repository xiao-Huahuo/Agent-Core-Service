/*
 * 会话导出子 Agent 事件回归测试。
 *
 * 用途：验证导出 YAML 的结构化消息中保留 `child_agent_event`，
 * 这样导出的会话再导入后能恢复子 Agent 事件条。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exportSession } from '@/utils/sessionExport'

const mocks = vi.hoisted(() => ({
  fetchMessages: vi.fn(),
  fetchSessionTaskList: vi.fn(),
  toYaml: vi.fn(),
}))

vi.mock('@/api/session', () => ({
  fetchMessages: mocks.fetchMessages,
}))

vi.mock('@/api/taskList', () => ({
  fetchSessionTaskList: mocks.fetchSessionTaskList,
}))

vi.mock('@/utils/yamlExport', () => ({
  toYaml: mocks.toYaml,
}))

describe('sessionExport child agent events', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchSessionTaskList.mockResolvedValue({ task_list: null })
    mocks.toYaml.mockReturnValue('session: test')
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:test'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  })

  it('keeps child_agent_event in exported messages', async () => {
    const childAgentEvent = {
      event_name: 'child_agent.completed',
      child: {
        run_id: 'child_run_1',
        goal: '整理资料',
        mode: 'background',
        status: 'completed',
        access_mode: 'readonly',
        allowed_tools: ['read_knowledge_file'],
        summary: '完成',
      },
    }
    mocks.fetchMessages.mockResolvedValue([
      {
        message_id: 'message-child',
        session_id: 'session-1',
        role: 'assistant',
        content: '子 Agent child_run_1 完成任务: 整理资料',
        created_at: '2026-08-01T00:00:00Z',
        metadata: { node: 'child_agent', child_agent_event: childAgentEvent },
        tool_calls: [],
      },
    ])

    await exportSession({
      session_id: 'session-1',
      user_id: 'user-1',
      session_name: '子 Agent 会话',
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-01T00:01:00Z',
    }, 'user-1')

    expect(mocks.toYaml).toHaveBeenCalledOnce()
    expect(mocks.toYaml.mock.calls[0]?.[0].messages[0].child_agent_event).toEqual(childAgentEvent)
  })
})
