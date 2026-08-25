/*
 * LaTeX preview lifecycle component tests.
 *
 * Usage:
 * Verifies explicit install consent, progress cancellation, compiler errors,
 * and successful reuse of the existing multimodal PDF viewer.
 */
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import LatexPreview from '../LatexPreview.vue'

const baseStatus = {
  status: 'missing' as const,
  stage: 'idle',
  progress: 0,
  message: '',
  source: 'none' as const,
  managed: false,
  runtime_path: 'C:/runtime/latex',
}

function mountPreview(props: Record<string, unknown>) {
  return mount(LatexPreview, {
    props: {
      status: baseStatus,
      result: null,
      compiling: false,
      ...props,
    },
    global: {
      stubs: {
        IcIcon: { template: '<span class="icon-stub"></span>' },
        MultimodalPreview: { props: ['preview'], template: '<div class="pdf-stub">{{ preview.kind }}</div>' },
      },
    },
  })
}

describe('LatexPreview', () => {
  afterEach(() => vi.restoreAllMocks())

  it('requires explicit confirmation before emitting install', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const wrapper = mountPreview({})

    await wrapper.get('.primary-action').trigger('click')
    await wrapper.get('.primary-action').trigger('click')

    expect(window.confirm).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('install')).toHaveLength(1)
  })

  it('shows backend install progress and emits cancellation', async () => {
    const wrapper = mountPreview({
      status: { ...baseStatus, status: 'installing', progress: 70, message: '正在安装 MiKTeX' },
    })

    expect(wrapper.text()).toContain('70%')
    await wrapper.get('.text-action.danger').trigger('click')
    expect(wrapper.emitted('cancelInstall')).toHaveLength(1)
  })

  it('renders source diagnostics and opens the selected compiler error', async () => {
    const error = { file: 'paper.tex', line: 12, message: 'Undefined control sequence' }
    const wrapper = mountPreview({
      status: { ...baseStatus, status: 'ready', source: 'system' },
      result: { success: false, path: 'paper.tex', root_path: 'paper.tex', output: 'log', errors: [error], preview: null },
    })

    await wrapper.get('.diagnostic-row').trigger('click')

    expect(wrapper.text()).toContain('paper.tex:12')
    expect(wrapper.emitted('openError')?.[0]).toEqual([error])
  })

  it('passes a successful compiled PDF to the existing preview component', () => {
    const wrapper = mountPreview({
      status: { ...baseStatus, status: 'ready', source: 'system' },
      result: {
        success: true,
        path: 'paper.tex',
        root_path: 'paper.tex',
        output: '',
        errors: [],
        preview: { kind: 'pdf', path: '.mw/latex/key/paper.pdf' },
      },
    })

    expect(wrapper.get('.pdf-stub').text()).toBe('pdf')
  })
})
