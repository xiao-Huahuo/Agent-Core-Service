/*
 * AgentConfig 全局常量面板测试。
 *
 * 使用说明:
 * 验证后端返回的动态配置组、字段介绍和值会完整展示,且页面不提供可修改控件。
 */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import GlobalConstantsPanel from '@/components/debug/GlobalConstantsPanel.vue'

vi.mock('@/api/debug', () => ({
  fetchGlobalConstants: vi.fn().mockResolvedValue({
    config_count: 1,
    constant_count: 2,
    configs: [
      {
        key: 'server',
        name: 'ServerConfig',
        description: '管理 HTTP 与 gRPC 服务。',
        constants: [
          {
            name: 'http_port',
            description: 'FastAPI HTTP 监听端口。',
            type: 'int',
            value: 8002,
          },
          {
            name: 'grpc_host',
            description: 'gRPC 监听地址。',
            type: 'str',
            value: '[::]',
          },
        ],
      },
    ],
  }),
}))

describe('GlobalConstantsPanel', () => {
  it('uses the tool registry hierarchy and component vocabulary without editable controls', async () => {
    const wrapper = mount(GlobalConstantsPanel, {
      global: {
        stubs: {
          IcIcon: true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('ServerConfig')
    expect(wrapper.text()).toContain('http_port')
    expect(wrapper.text()).toContain('FastAPI HTTP 监听端口。')
    expect(wrapper.text()).toContain('8002')
    expect(wrapper.find('.registry-grid').exists()).toBe(true)
    expect(wrapper.find('.category-header').exists()).toBe(true)
    expect(wrapper.findAll('.tool-list-item')).toHaveLength(2)
    expect(wrapper.find('.tool-detail').exists()).toBe(true)
    expect(wrapper.find('.arg-table').exists()).toBe(true)
    expect(wrapper.find('.schema-block').exists()).toBe(true)
    expect(wrapper.find('.constants-grid').exists()).toBe(false)
    expect(wrapper.find('.config-row').exists()).toBe(false)
    expect(wrapper.find('.constant-table').exists()).toBe(false)
    expect(wrapper.findAll('input')).toHaveLength(1)
    expect(wrapper.find('input').attributes('placeholder')).toBe('搜索常量')
    expect(wrapper.find('textarea').exists()).toBe(false)

    await wrapper.findAll('.tool-row')[1]!.trigger('click')
    expect(wrapper.text()).toContain('gRPC 监听地址。')
    expect(wrapper.text()).toContain('[::]')
  })
})
