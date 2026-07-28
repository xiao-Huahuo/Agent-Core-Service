/*
 * Chat input reference regression tests.
 *
 * Verifies that sending captures the visible reference before the input clears it.
 */
import { afterEach, describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import ChatInput from '../ChatInput.vue'

describe('ChatInput references', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('emits a snapshot of the reference with the user prompt', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        reference: '  被引用的文档内容  ',
      },
    })

    await wrapper.get('textarea').setValue('引用内容是什么意思?')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toEqual([
      ['引用内容是什么意思?', '被引用的文档内容'],
    ])
    expect(wrapper.emitted('clear-reference')).toHaveLength(1)
  })

  it('emits the selected Agent access mode from the permission menu', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        agentAccessMode: 'sandbox',
      },
    })

    const details = wrapper.get('.access-mode-dropdown')
    ;(details.element as HTMLDetailsElement).open = true
    await details.trigger('toggle')
    await nextTick()

    const fullAccessButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.access-mode-option'))
      .find((button) => button.textContent?.includes('完全访问'))

    expect(fullAccessButton).toBeTruthy()
    fullAccessButton?.click()
    await nextTick()

    expect(wrapper.emitted('set-agent-access-mode')).toEqual([['full_access']])
  })

  it('injects a starter prefix without sending the prompt', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        centered: true,
      },
    })

    const starter = wrapper
      .findAll('.prompt-starter-card')
      .find((button) => button.text().includes('探索并理解代码'))

    expect(starter).toBeTruthy()
    await starter?.trigger('click')

    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('探索')
    expect(wrapper.emitted('send')).toBeFalsy()
    expect(wrapper.findAll('.prompt-starter-card')).toHaveLength(0)
    expect(wrapper.findAll('.prompt-waterfall-item')).toHaveLength(4)
  })

  it('matches suggestions against the current input prefix', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        centered: true,
      },
    })

    const buildStarter = wrapper
      .findAll('.prompt-starter-card')
      .find((button) => button.text().includes('构建新功能应用或工具'))

    await buildStarter?.trigger('click')
    const suggestion = wrapper
      .findAll('.prompt-waterfall-item')
      .find((button) => button.text().includes('构建一个新功能并接入现有界面'))

    expect(suggestion).toBeTruthy()
    await suggestion?.trigger('click')

    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('构建一个新功能并接入现有界面')
    expect(wrapper.emitted('send')).toBeFalsy()
    expect(wrapper.findAll('.prompt-waterfall-item')).toHaveLength(1)
  })

  it('returns to starter cards when the prompt prefix is cleared', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        centered: true,
      },
    })

    const fixStarter = wrapper
      .findAll('.prompt-starter-card')
      .find((button) => button.text().includes('修复问题和失败'))

    await fixStarter?.trigger('click')
    expect(wrapper.findAll('.prompt-waterfall-item')).toHaveLength(4)

    await wrapper.get('textarea').setValue('')

    expect(wrapper.findAll('.prompt-waterfall-item')).toHaveLength(0)
    expect(wrapper.findAll('.prompt-starter-card')).toHaveLength(4)
  })
})
