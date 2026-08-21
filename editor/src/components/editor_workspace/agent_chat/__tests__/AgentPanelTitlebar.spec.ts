/** Shared Agent titlebar contract for sidebar and floating surfaces. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AgentPanelTitlebar from '../AgentPanelTitlebar.vue'

describe('AgentPanelTitlebar', () => {
  it('renders and emits the shared Agent controls', async () => {
    const wrapper = mount(AgentPanelTitlebar, {
      props: { title: '同步会话', chatMode: 'tool' },
    })

    expect(wrapper.text()).toContain('同步会话')
    expect(wrapper.text()).toContain('新对话')
    expect(wrapper.text()).toContain('tool')
    await wrapper.get('button[title="会话"]').trigger('click')
    await wrapper.get('button[title="任务列表"]').trigger('click')
    expect(wrapper.emitted('toggleSessions')).toHaveLength(1)
    expect(wrapper.emitted('toggleTask')).toHaveLength(1)
  })

  it('reaches the floating window through complete AgentPanel reuse', () => {
    const sidebarSource = readFileSync(resolve(process.cwd(), 'src/components/editor_workspace/AgentPanel.vue'), 'utf8')
    const floatingSource = readFileSync(resolve(process.cwd(), 'src/components/floating/FloatingAgent.vue'), 'utf8')

    expect(sidebarSource).toContain('<AgentPanelTitlebar')
    expect(floatingSource).toContain('<AgentPanel')
    expect(floatingSource).not.toContain('<MessageList')
    expect(floatingSource).not.toContain('<AgentPanelTitlebar')
  })
})
