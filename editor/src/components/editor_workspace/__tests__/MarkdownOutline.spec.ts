/*
 * Markdown outline sidebar interaction tests.
 *
 * Verifies the supplied checkbox tree controls, title search emphasis, and
 * navigation emission used by the editor pane.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MarkdownOutline from '../MarkdownOutline.vue'
import { parseMarkdownOutline } from '../markdownOutline'

const items = parseMarkdownOutline('# Guide\n## Install\n### Windows\n## Usage')

describe('MarkdownOutline', () => {
  it('expands, collapses, and searches heading text with bold matches', async () => {
    const wrapper = mount(MarkdownOutline, {
      props: { items, activeId: items[0]!.id, open: true },
    })

    expect(wrapper.findAll('.tree-item')).toHaveLength(4)
    expect(wrapper.findAll('.tree-label')).toHaveLength(2)
    expect(wrapper.findAll('.file-item')).toHaveLength(2)
    await wrapper.findAll('.outline-actions button')[1]!.trigger('click')
    expect(wrapper.findAll<HTMLInputElement>('.tree-toggle').every((input) => !input.element.checked)).toBe(true)
    await wrapper.findAll('.outline-actions button')[0]!.trigger('click')
    expect(wrapper.findAll<HTMLInputElement>('.tree-toggle').every((input) => input.element.checked)).toBe(true)

    await wrapper.get('input[type="search"]').setValue('win')
    expect(wrapper.findAll('.tree-name').map((item) => item.text())).toEqual(['Guide', 'Install', 'Windows'])
    expect(wrapper.get('.tree-name strong').text()).toBe('Win')
  })

  it('marks the current heading and emits the selected heading', async () => {
    const active = items[0]!.children[0]!
    const wrapper = mount(MarkdownOutline, {
      props: { items, activeId: active.id, open: true },
    })

    expect(wrapper.get('.is-selected').text()).toContain('Install')
    await wrapper.findAll('.file-item')[1]!.trigger('click')
    expect(wrapper.emitted('navigate')?.[0]?.[0]).toMatchObject({ text: 'Usage' })
  })
})
