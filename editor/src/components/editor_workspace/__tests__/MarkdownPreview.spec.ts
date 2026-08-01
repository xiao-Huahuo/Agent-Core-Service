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
})
