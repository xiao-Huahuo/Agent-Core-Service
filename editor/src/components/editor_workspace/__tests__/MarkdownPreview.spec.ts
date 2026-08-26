/*
 * Markdown preview component tests.
 *
 * Usage:
 * Verifies editor-facing preview behavior without booting a real Vditor
 * instance. These tests focus on synchronization contracts that Split mode
 * depends on.
 */

import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarkdownPreview from '../MarkdownPreview.vue'

const vditorMocks = vi.hoisted(() => {
  const previewElement = document.createElement('div')
  previewElement.className = 'vditor-preview'
  const instance = {
    vditor: {
      preview: {
        element: previewElement,
      },
    },
    disabledCache: vi.fn(),
    clearCache: vi.fn(),
    getValue: vi.fn(() => 'initial'),
    setValue: vi.fn(),
    renderPreview: vi.fn(),
    destroy: vi.fn(),
  }
  const constructor = vi.fn(function VditorMock(_element: HTMLElement, options: Record<string, unknown>) {
    constructor.options = options
    return instance
  }) as unknown as ReturnType<typeof vi.fn> & { options?: Record<string, unknown> }

  return { constructor, instance, previewElement }
})

vi.mock('vditor', () => ({ default: vditorMocks.constructor }))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    profile: {
      userId: '1',
    },
  }),
}))

vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: () => ({
    selectedPath: 'notes/test.md',
    tree: [
      { name: 'target.md', path: 'notes/target.md', isDir: false },
    ],
  }),
}))

vi.mock('@/components/common/useImagePreviewer', () => ({
  useImagePreviewer: () => ({
    open: vi.fn(),
  }),
}))

describe('MarkdownPreview Split synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vditorMocks.instance.getValue.mockReturnValue('initial')
    vditorMocks.previewElement.innerHTML = ''
    vditorMocks.previewElement.scrollTop = 0
  })

  it('renders immediately when content changes instead of waiting for animation frame', async () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: 'initial',
        path: 'notes/test.md',
      },
    })
    const options = vditorMocks.constructor.options
    const after = options?.after as (() => void) | undefined
    expect(after).toBeTypeOf('function')
    after?.()
    await nextTick()
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))

    const frameSpy = vi.spyOn(window, 'requestAnimationFrame')
    vditorMocks.instance.setValue.mockClear()
    vditorMocks.instance.renderPreview.mockClear()
    vditorMocks.instance.getValue.mockReturnValue('initial')

    await wrapper.setProps({ content: 'updated **markdown**' })

    expect(vditorMocks.instance.setValue).toHaveBeenCalledWith('updated **markdown**', true)
    expect(vditorMocks.instance.renderPreview).toHaveBeenCalledTimes(1)
    expect(frameSpy).not.toHaveBeenCalled()

    frameSpy.mockRestore()
  })

  it('renders ==text== as mark while preserving inline and fenced code', () => {
    mount(MarkdownPreview, {
      props: {
        content: 'plain ==marked== and `==inline==`\n\n```md\n==fenced==\n```',
        path: 'notes/test.md',
      },
    })

    const value = vditorMocks.constructor.options?.value as string
    expect(value).toContain('plain <mark>marked</mark>')
    expect(value).toContain('`==inline==`')
    expect(value).toContain('```md\n==fenced==\n```')
  })

  it('anchors the rendered block at the caret viewport position', () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: '# First\n\nMiddle\n\nLast',
        path: 'notes/test.md',
      },
    })
    const host = wrapper.get('.markdown-preview-renderer').element as HTMLElement
    vditorMocks.previewElement.innerHTML = '<div class="vditor-reset"><h1>First</h1><p>Middle</p><p>Last</p></div>'
    host.appendChild(vditorMocks.previewElement)
    const target = vditorMocks.previewElement.querySelectorAll('p')[1] as HTMLElement
    Object.defineProperties(vditorMocks.previewElement, {
      clientHeight: { configurable: true, value: 300 },
      scrollHeight: { configurable: true, value: 900 },
      scrollTop: { configurable: true, writable: true, value: 200 },
      getBoundingClientRect: { configurable: true, value: () => ({ left: 0, top: 100, width: 500, height: 300, right: 500, bottom: 400 }) },
    })
    Object.defineProperty(target, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 0, top: 500, width: 200, height: 30, right: 200, bottom: 530 }),
    })

    ;(wrapper.vm as unknown as { scrollToSourceOffset: (offset: number, contentLength: number, behavior: ScrollBehavior, viewportRatio: number) => void })
      .scrollToSourceOffset(24, 24, 'auto', 0.4)

    expect(vditorMocks.previewElement.scrollTop).toBe(480)
  })

  it('smoothly scrolls to a rendered outline heading and reports it as active', () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: '# Guide\n\n## Usage',
        path: 'notes/test.md',
      },
    })
    const host = wrapper.get('.markdown-preview-renderer').element as HTMLElement
    vditorMocks.previewElement.innerHTML = '<div class="vditor-reset"><h1>Guide</h1><h2>Usage</h2></div>'
    host.appendChild(vditorMocks.previewElement)
    const target = vditorMocks.previewElement.querySelector('h2') as HTMLElement
    Object.defineProperty(vditorMocks.previewElement, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 0, top: 0, width: 500, height: 300, right: 500, bottom: 300 }),
    })
    Object.defineProperty(target, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 0, top: 420, width: 200, height: 30, right: 200, bottom: 450 }),
    })
    const scrollTo = vi.fn()
    Object.defineProperty(vditorMocks.previewElement, 'scrollTo', { configurable: true, value: scrollTo })

    ;(wrapper.vm as unknown as { scrollToHeading: (index: number) => void }).scrollToHeading(1)

    expect(scrollTo).toHaveBeenCalledWith({ top: 408, behavior: 'smooth' })
    expect(wrapper.emitted('activeHeading')?.at(-1)?.[0]).toBe(1)
  })

  it('emits updated Markdown when adding a row from a rendered preview table', async () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: '| A | B |\n| --- | --- |\n| 1 | 2 |',
        path: 'notes/test.md',
      },
    })
    const host = wrapper.get('.markdown-preview-renderer').element as HTMLElement
    host.appendChild(vditorMocks.previewElement)
    vditorMocks.previewElement.innerHTML = '<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>'
    const table = vditorMocks.previewElement.querySelector('table') as HTMLTableElement
    const headerRow = table.rows[0] as HTMLTableRowElement
    const bodyRow = table.rows[1] as HTMLTableRowElement
    const cell = table.querySelector('tbody td') as HTMLTableCellElement
    const headerCells = [...table.querySelectorAll<HTMLTableCellElement>('thead th')]
    const bodyCells = [...table.querySelectorAll<HTMLTableCellElement>('tbody td')]
    Object.defineProperty(host, 'getBoundingClientRect', { value: () => ({ left: 0, top: 0, width: 400, height: 200, right: 400, bottom: 200 }) })
    Object.defineProperty(table, 'getBoundingClientRect', { value: () => ({ left: 20, top: 20, width: 280, height: 60, right: 300, bottom: 80 }) })
    Object.defineProperty(headerRow, 'getBoundingClientRect', { value: () => ({ left: 20, top: 20, width: 200, height: 30, right: 220, bottom: 50 }) })
    Object.defineProperty(bodyRow, 'getBoundingClientRect', { value: () => ({ left: 20, top: 50, width: 200, height: 30, right: 220, bottom: 80 }) })
    Object.defineProperty(headerCells[0], 'getBoundingClientRect', { value: () => ({ left: 20, top: 20, width: 100, height: 30, right: 120, bottom: 50 }) })
    Object.defineProperty(headerCells[1], 'getBoundingClientRect', { value: () => ({ left: 120, top: 20, width: 100, height: 30, right: 220, bottom: 50 }) })
    Object.defineProperty(cell, 'getBoundingClientRect', { value: () => ({ left: 20, top: 50, width: 100, height: 30, right: 120, bottom: 80 }) })
    Object.defineProperty(bodyCells[1], 'getBoundingClientRect', { value: () => ({ left: 120, top: 50, width: 100, height: 30, right: 220, bottom: 80 }) })

    cell.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 80, clientY: 60 }))
    await nextTick()
    expect(wrapper.find('.markdown-preview-table-overlay').exists()).toBe(false)

    const previewSurface = wrapper.get('.markdown-preview').element as HTMLElement
    previewSurface.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 30, clientY: 84 }))
    await nextTick()
    const overlay = wrapper.get('.markdown-preview-table-overlay').element as HTMLElement
    expect(overlay.style.left).toBe('20px')
    expect(overlay.style.width).toBe('200px')
    expect(wrapper.find('.preview-table-add-row-button').exists()).toBe(true)
    expect(wrapper.find('.preview-table-column-drag-handle').exists()).toBe(false)
    overlay.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 18, clientY: 60 }))
    await nextTick()
    expect(wrapper.find('.preview-table-add-row-button').exists()).toBe(true)

    await wrapper.get('.preview-table-add-row-button').trigger('click')

    expect(wrapper.emitted('updateContent')?.[0]?.[0]).toBe('| A | B |\n| --- | --- |\n| 1 | 2 |\n|   |   |')
  })

  it('decorates a wiki link after parsing and emits its navigation destination', async () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: '[[target#章节|阅读章节]]',
        path: 'notes/test.md',
      },
    })
    const host = wrapper.get('.markdown-preview-renderer').element as HTMLElement
    const reset = document.createElement('div')
    reset.className = 'vditor-reset'
    reset.textContent = '[[target#章节|阅读章节]]'
    vditorMocks.previewElement.appendChild(reset)
    host.appendChild(vditorMocks.previewElement)

    const parse = (vditorMocks.constructor.options?.preview as { parse?: (element: HTMLElement) => void })?.parse
    parse?.(vditorMocks.previewElement)
    await Promise.resolve()

    const link = reset.querySelector<HTMLAnchorElement>('.wiki-link')
    expect(link?.textContent).toBe('阅读章节')
    link?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(wrapper.emitted('navigateWiki')?.[0]).toEqual(['target#章节|阅读章节'])
  })

  it('renders HTML img and iframe elements as responsive media blocks', async () => {
    const wrapper = mount(MarkdownPreview, {
      props: {
        content: '<img src="./cover.png" alt="封面">\n\n<iframe src="https://video.example/embed/1"></iframe>',
        path: 'notes/test.md',
      },
    })
    const host = wrapper.get('.markdown-preview-renderer').element as HTMLElement
    const reset = document.createElement('div')
    reset.className = 'vditor-reset'
    reset.innerHTML = '<img src="./cover.png" alt="封面"><iframe src="https://video.example/embed/1"></iframe>'
    vditorMocks.previewElement.appendChild(reset)
    host.appendChild(vditorMocks.previewElement)

    const previewOptions = vditorMocks.constructor.options?.preview as {
      parse?: (element: HTMLElement) => void
      render?: { media?: { enable?: boolean } }
    }
    previewOptions.parse?.(vditorMocks.previewElement)
    await Promise.resolve()

    expect(previewOptions.render?.media?.enable).toBe(true)
    expect(reset.querySelector('img')?.classList.contains('markdown-html-image-block')).toBe(true)
    const iframe = reset.querySelector('iframe')
    expect(iframe?.classList.contains('markdown-video-block')).toBe(true)
    expect(iframe?.getAttribute('loading')).toBe('lazy')
    expect(iframe?.getAttribute('allowfullscreen')).not.toBeNull()
  })
})
