/*
 * Smart Markdown cell interaction tests.
 *
 * Usage:
 * Run with Vitest to verify editing and clipboard image insertion without a
 * live knowledge backend or a full Vditor instance.
 */

import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SmartMarkdownCell from '@/components/smart_forms/SmartMarkdownCell.vue'

describe('SmartMarkdownCell', () => {
  it('uploads pasted images and emits form-relative Markdown', async () => {
    const image = new File(['image'], 'clipboard.png', { type: 'image/png' })
    const uploadImage = vi.fn().mockResolvedValue({ name: 'clipboard.png', relativePath: 'assets/clipboard.png' })
    const wrapper = mount(SmartMarkdownCell, {
      props: { value: '说明', path: 'forms/demo/table.md', editable: true, uploadImage },
      global: {
        stubs: {
          MarkdownContent: { template: '<div class="markdown-body"></div>' },
          MarkdownPreview: { template: '<div class="markdown-preview"></div>' },
        },
      },
    })
    const event = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(event, 'clipboardData', {
      value: { items: [{ kind: 'file', type: 'image/png', getAsFile: () => image }] },
    })

    wrapper.get('.smart-markdown-cell').element.dispatchEvent(event)
    await flushPromises()

    expect(uploadImage).toHaveBeenCalledWith(image)
    expect(wrapper.emitted('update')?.at(-1)).toEqual(['说明\n![clipboard.png](assets/clipboard.png)'])
  })

  it('shows rendered Markdown until an editable cell is double-clicked', async () => {
    const wrapper = mount(SmartMarkdownCell, {
      props: { value: '**重点**', path: 'forms/demo/table.md', editable: true, uploadImage: vi.fn() },
      global: { stubs: { MarkdownContent: { template: '<div class="markdown-body"></div>' } } },
    })

    expect((wrapper.get('textarea').element as HTMLTextAreaElement).style.display).toBe('none')
    await wrapper.get('.smart-markdown-cell').trigger('dblclick')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).style.display).toBe('')
    expect(wrapper.get('textarea').attributes('rows')).toBe('1')
  })

  it('keeps editing when the active cell is clicked again', async () => {
    const wrapper = mount(SmartMarkdownCell, {
      props: { value: '可编辑内容', path: 'forms/demo/table.md', editable: true, uploadImage: vi.fn() },
      global: { stubs: { MarkdownContent: { template: '<div class="markdown-body"></div>' } } },
    })

    const cell = wrapper.get('.smart-markdown-cell')
    await cell.trigger('dblclick')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).style.display).toBe('')

    await wrapper.get('textarea').trigger('click')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).style.display).toBe('')
  })

  it('truncates long text and expands it with a resize event', async () => {
    const value = 'a'.repeat(240)
    const wrapper = mount(SmartMarkdownCell, {
      props: { value, path: 'forms/demo/table.md', editable: true, uploadImage: vi.fn() },
      global: {
        stubs: {
          MarkdownContent: { props: ['content'], template: '<div class="markdown-body">{{ content }}</div>' },
        },
      },
    })

    expect(wrapper.get('.markdown-body').text()).toBe(`${'a'.repeat(200)}...`)
    await wrapper.get('.smart-markdown-toggle').trigger('click')

    expect(wrapper.get('.markdown-body').text()).toBe(value)
    expect(wrapper.emitted('resize')?.[0]).toEqual([true, 282])
  })

  it('keeps expanded content visible while emitting the closing resize', async () => {
    vi.useFakeTimers()
    const value = 'a'.repeat(240)
    const wrapper = mount(SmartMarkdownCell, {
      props: { value, path: 'forms/demo/table.md', editable: true, uploadImage: vi.fn() },
      global: {
        stubs: {
          MarkdownContent: { props: ['content'], template: '<div class="markdown-body">{{ content }}</div>' },
        },
      },
    })

    await wrapper.get('.smart-markdown-toggle').trigger('click')
    await wrapper.get('.smart-markdown-toggle').trigger('click')

    const resizeEvents = wrapper.emitted('resize') ?? []
    expect(resizeEvents[resizeEvents.length - 1]).toEqual([false, 282])
    expect(wrapper.get('.markdown-body').text()).toBe(value)
    await vi.runAllTimersAsync()
    expect(wrapper.get('.markdown-body').text()).toBe(`${'a'.repeat(200)}...`)
    vi.useRealTimers()
  })
})
