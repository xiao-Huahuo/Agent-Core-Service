/*
 * PDF preview toolbar download tests.
 *
 * Usage:
 * Ensures compiled LaTeX PDFs expose a same-name download action while normal
 * knowledge PDFs keep the existing toolbar unchanged.
 */
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import PdfPreview from '../PdfPreview.vue'

class ObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const basePreview = {
  kind: 'pdf' as const,
  path: '.mw/latex/key/paper.pdf',
  raw_url: '/knowledge/files/raw?user_id=u1&path=.mw%2Flatex%2Fkey%2Fpaper.pdf',
  pdf_pages: [],
  mtime: '2026-08-25',
  size: 4,
  extension: '.pdf',
  readonly: true,
}

describe('PdfPreview compiled LaTeX download', () => {
  beforeEach(() => {
    vi.stubGlobal('IntersectionObserver', ObserverStub)
    vi.stubGlobal('ResizeObserver', ObserverStub)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('downloads a compiled TeX PDF through the existing raw endpoint', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const wrapper = mount(PdfPreview, {
      props: { preview: basePreview, source: basePreview.raw_url },
    })

    await wrapper.get('.pdf-download-button').trigger('click')

    expect(click).toHaveBeenCalledOnce()
    const anchor = click.mock.instances[0] as HTMLAnchorElement | undefined
    expect(anchor?.download).toBe('paper.pdf')
    expect(anchor?.href).toContain('download=true')
  })

  it('does not add a download action to ordinary knowledge PDF previews', () => {
    const wrapper = mount(PdfPreview, {
      props: { preview: { ...basePreview, path: 'papers/report.pdf' }, source: '/knowledge/files/raw?path=papers/report.pdf' },
    })

    expect(wrapper.find('.pdf-download-button').exists()).toBe(false)
  })
})
