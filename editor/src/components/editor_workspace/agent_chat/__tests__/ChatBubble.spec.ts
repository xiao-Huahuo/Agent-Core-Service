/*
 * User chat bubble reference regression tests.
 *
 * Verifies that quoted document text is rendered with the user's message.
 */
import { describe, expect, it, vi } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ChatBubble from '../ChatBubble.vue'
import MessageBubble from '../MessageBubble.vue'
import MessageList from '../MessageList.vue'
import ToolBubble from '../ToolBubble.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

describe('ChatBubble user references', () => {
  it('renders a persisted child completion wakeup as an Agent event instead of a user bubble', () => {
    const wrapper = mount(MessageBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: {
          role: 'user',
          content: '内部自动唤醒提示',
          metadata: {
            wakeup: true,
            child_agent_event: {
              event_name: 'child_agent.completed',
              child: {
                run_id: 'child-1', goal: '检索资料', mode: 'background', status: 'completed',
                access_mode: 'readonly', allowed_tools: [], name: 'explore1',
              },
            },
          },
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })

    expect(wrapper.get('.child-agent-event').text()).toContain('子 Agent 完成任务：explore1')
    expect(wrapper.find('.bubble.user').exists()).toBe(false)
  })

  it.each(['chat', 'tool'] as const)('renders full-date separators only at 30-minute boundaries in %s mode', (mode) => {
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { value: vi.fn(), configurable: true, writable: true })
    const pinia = createPinia()
    setActivePinia(pinia)
    useSettingsStore().$patch({ chatMode: mode })
    const wrapper = mount(MessageList, {
      global: { plugins: [pinia] },
      props: {
        messages: [
          { message_id: 'm1', role: 'user', content: '第一条', created_at: '2026-08-30T08:01:00' },
          { message_id: 'm2', role: 'assistant', content: '相隔不足三十分钟', node: 'agent', created_at: '2026-08-30T08:30:59' },
          { message_id: 'm3', role: 'user', content: '正好相隔三十分钟', created_at: '2026-08-30T09:00:59' },
          { message_id: 'm4', role: 'assistant', content: '缺失有效时间', node: 'agent', created_at: 'invalid' },
        ],
      },
    })

    expect(wrapper.findAll('.message-time-separator').map((item) => item.text())).toEqual([
      '2026年08月30日 08:01',
      '2026年08月30日 09:00',
    ])
    expect(wrapper.findAll('.message-time')).toHaveLength(0)
  })

  it('renders the reference above the user message', () => {
    const wrapper = mount(ChatBubble, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        message: {
          role: 'user',
          content: '请解释这段话',
          reference: '被引用的文档内容',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })

    const referenceBlock = wrapper.get('.reference-block')
    const userBubble = wrapper.get('.bubble.user')
    expect(referenceBlock.text()).toBe('被引用的文档内容')
    expect(referenceBlock.element.compareDocumentPosition(userBubble.element) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
    expect(wrapper.get('.bubble.user').text()).toBe('请解释这段话')
  })

  it('renders assistant thinking duration above final content', () => {
    const wrapper = mount(ChatBubble, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        message: {
          role: 'assistant',
          content: '你好，我在。',
          node: 'agent',
          thinking_seconds: 3.6,
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: false,
      },
    })

    expect(wrapper.get('.thinking-summary').text()).toContain('思考了 3.6s')
  })

  it('shows assistant metadata only on the final answer of each user turn', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent', thinking_seconds: 1.1 },
          { role: 'assistant', content: '', node: 'child_agent' },
          { role: 'assistant', content: '最终答案', node: 'agent', thinking_seconds: 2.2 },
          { role: 'user', content: '第二个问题' },
          { role: 'assistant', content: '第二轮答案', node: 'agent', thinking_seconds: 3.3 },
        ],
        isStreaming: false,
      },
    })

    expect(wrapper.findAll('.message-actions')).toHaveLength(2)
    expect(wrapper.findAll('.thinking-summary').map((item) => item.text().replace(/\s+/g, ' ').trim())).toEqual([
      '思考了 2.2s',
      '思考了 3.3s',
    ])
  })

  it('appends the three follow-up suggestions below the latest assistant answer', async () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '第一轮答案', node: 'agent' },
          { role: 'user', content: '继续' },
          { role: 'assistant', content: '最新答案', node: 'agent' },
        ],
        suggestions: ['检查结果', '继续优化', '解释改动'],
      },
    })

    const suggestions = wrapper.get('.task-suggestions')
    expect(suggestions.findAll('.suggestion-button')).toHaveLength(3)
    const latestAssistant = wrapper.findAll('.bubble-row.assistant')[1]
    const suggestionButtons = suggestions.findAll('.suggestion-button')
    if (!latestAssistant || !suggestionButtons[1]) throw new Error('latest Agent response suggestions were not rendered')
    expect(latestAssistant.element.compareDocumentPosition(suggestions.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await suggestionButtons[1].trigger('click')
    expect(wrapper.emitted('select-suggestion')).toEqual([['继续优化']])
  })

  it('keeps the message list pinned when follow-up suggestions arrive asynchronously', async () => {
    const scrollTo = vi.fn()
    HTMLElement.prototype.scrollTo = scrollTo
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '最新答案', node: 'agent' },
        ],
        suggestions: [],
      },
    })
    scrollTo.mockClear()

    await wrapper.setProps({ suggestions: ['检查结果', '继续优化', '解释改动'] })
    await wrapper.vm.$nextTick()

    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: expect.any(Number) }))
  })

  it('keeps one avatar on the latest assistant item in a user turn', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent' },
          { role: 'assistant', content: '最终答案', node: 'agent' },
        ],
      },
    })

    expect(wrapper.findAll('img[alt="agent"]')).toHaveLength(1)
  })

  it('keeps the avatar on a completed final assistant reply', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent' },
          { role: 'assistant', content: '最终答案', node: 'agent' },
        ],
        isStreaming: false,
      },
    })

    expect(wrapper.findAll('img[alt="agent"]')).toHaveLength(1)
  })

  it('keeps an empty avatar column for consecutive assistant entries', () => {
    const wrapper = mount(ToolBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '中间输出' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        showAvatar: false,
      },
    })

    expect(wrapper.find('.avatar-slot').exists()).toBe(true)
    expect(wrapper.find('img[alt="agent"]').exists()).toBe(false)
  })

  it('shows the pixel loading state before the assistant placeholder arrives', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [{ role: 'user', content: '请开始' }],
        isStreaming: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.loading-state__label').classes()).toContain('thinking-shimmer-text')
    expect(wrapper.findAll('.pixel')).toHaveLength(9)
    expect(wrapper.find('.thinking-spinner svg').exists()).toBe(true)
    expect(wrapper.find('.thinking-loader').exists()).toBe(false)
  })

  it('shows the pixel loading state instead of a cursor for an empty assistant stream', () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        showAvatar: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.cursor').exists()).toBe(false)
    expect(wrapper.find('.bubble.assistant').exists()).toBe(false)
  })

  it('shows the pixel loading state instead of a cursor in tool mode', () => {
    const wrapper = mount(ToolBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        showAvatar: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.cursor').exists()).toBe(false)
    expect(wrapper.find('.assistant-article').exists()).toBe(false)
    expect(wrapper.get('.avatar').attributes('src')).toBe('agent.png')
  })

  it('reveals sources and message actions only after streaming completes', async () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '带来源的回答' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        knowledgeSources: [{ source_uri: 'notes/source.md', title: '来源文档', content: '' }],
      },
    })

    expect(wrapper.find('.message-actions').exists()).toBe(false)
    expect(wrapper.find('.knowledge-sources').exists()).toBe(false)

    await wrapper.setProps({ isStreaming: false })

    expect(wrapper.find('.message-actions').exists()).toBe(true)
    expect(wrapper.find('.knowledge-sources').exists()).toBe(true)
  })

  it('opens HTTP [N] citations in the shared right-side browser', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ChatBubble, {
      global: { plugins: [pinia] },
      props: {
        message: { role: 'assistant', content: '网页来源 [1]', node: 'agent' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        citationMap: { 1: { source_uri: 'https://example.com/source', content: '' } },
      },
    })

    await wrapper.get('.citation-anchor').trigger('click')

    const workspaceStore = useWorkspaceStore()
    expect(workspaceStore.browserSidebarOpen).toBe(true)
    expect(workspaceStore.browserSidebarUrl).toBe('https://example.com/source')
  })

  it('opens a mounted local file in the main editor from sidebar mode', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const workspaceStore = useWorkspaceStore()
    const node = { name: '简单word.docx', path: '文档/简单word.docx', isDir: false }
    workspaceStore.tree = [node]
    workspaceStore.mainView = 'editor'
    const selectFile = vi.spyOn(workspaceStore, 'selectFile').mockResolvedValue()

    const wrapper = mount(ChatBubble, {
      global: { plugins: [pinia] },
      props: {
        message: {
          role: 'assistant',
          content: '[打开《简单word.docx》](/knowledge/files/raw?user_id=1&path=%E6%96%87%E6%A1%A3%2F%E7%AE%80%E5%8D%95word.docx)',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    await wrapper.get('.agent-mounted-file').trigger('click')
    expect(selectFile).toHaveBeenCalledWith(node)
    expect(workspaceStore.editorSidebarOpen).toBe(false)
  })

  it('opens a mounted local file in the main editor from tool sidebar mode', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const workspaceStore = useWorkspaceStore()
    const node = { name: '简单word.docx', path: '文档/简单word.docx', isDir: false }
    workspaceStore.tree = [node]
    workspaceStore.mainView = 'editor'
    const selectFile = vi.spyOn(workspaceStore, 'selectFile').mockResolvedValue()

    const wrapper = mount(ToolBubble, {
      global: { plugins: [pinia] },
      props: {
        message: {
          role: 'assistant',
          content: '[打开《简单word.docx》](/knowledge/files/raw?user_id=1&path=%E6%96%87%E6%A1%A3%2F%E7%AE%80%E5%8D%95word.docx)',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    await wrapper.get('.agent-mounted-file').trigger('click')
    expect(selectFile).toHaveBeenCalledWith(node)
    expect(workspaceStore.editorSidebarOpen).toBe(false)
  })

  it('keeps mounted-file navigation in the editor sidebar on the Agent page', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const workspaceStore = useWorkspaceStore()
    const node = { name: '简单word.docx', path: '文档/简单word.docx', isDir: false }
    workspaceStore.tree = [node]
    workspaceStore.mainView = 'agent'
    const openEditorSidebar = vi.spyOn(workspaceStore, 'openEditorSidebar').mockResolvedValue()

    const wrapper = mount(ChatBubble, {
      global: { plugins: [pinia] },
      props: {
        message: {
          role: 'assistant',
          content: '[打开《简单word.docx》](/knowledge/files/raw?user_id=1&path=%E6%96%87%E6%A1%A3%2F%E7%AE%80%E5%8D%95word.docx)',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    await wrapper.get('.agent-mounted-file').trigger('click')
    expect(openEditorSidebar).toHaveBeenCalledWith(node)
  })

  it('renders a DSH-style Think row above completed assistant content', () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: {
          role: 'assistant',
          content: '最终回答',
          node: 'agent',
          thinking: '第一步先检查调用链\n第二步再修改',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: false,
      },
    })

    const thinkRow = wrapper.get('[data-variant="think"]')
    expect(thinkRow.attributes('data-state')).toBe('ok')
    expect(thinkRow.text()).toContain('思考')
    // 完成后摘要固定显示第一行
    expect(thinkRow.text()).toContain('第一步先检查调用链')
  })

  it('follows the latest thinking line while the turn is streaming', () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: {
          role: 'assistant',
          content: '',
          node: 'agent',
          thinking: '第一行\n第二行思考中',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
      },
    })

    const thinkRow = wrapper.get('[data-variant="think"]')
    expect(thinkRow.attributes('data-state')).toBe('running')
    expect(thinkRow.text()).toContain('第二行思考中')
  })

  it('expands the full thinking text on row click', async () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: {
          role: 'assistant',
          content: '最终回答',
          node: 'agent',
          thinking: '完整思考内容第一行\n完整思考内容第二行',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: false,
      },
    })

    expect(wrapper.find('.think-row__body').exists()).toBe(false)
    await wrapper.get('.think-row__trigger').trigger('click')
    expect(wrapper.get('.think-row__body').text()).toBe('完整思考内容第一行\n完整思考内容第二行')
  })

  it('renders the Think row in tool mode as well', () => {
    const wrapper = mount(ToolBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: {
          role: 'assistant',
          content: '工具模式回答',
          node: 'agent',
          thinking: '工具模式思考',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: false,
      },
    })

    expect(wrapper.get('[data-variant="think"]').text()).toContain('工具模式思考')
  })
})
