/* Per-file attachment parsing progress rendering tests. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AttachmentBlocks from '../AttachmentBlocks.vue'

describe('AttachmentBlocks', () => {
  it('shows parsing progress only inside the matching attachment card', () => {
    const wrapper = mount(AttachmentBlocks, {
      props: {
        attachments: [{
          attachment_id: 'att-1', user_id: 'u1', session_id: 's1', library_id: '', library_name: '',
          filename: 'diagram.png', stored_name: 'diagram.png', uri: '', mime_type: 'image/png', size: 12,
          source_type: 'processing', created_at: '',
          metadata: { processing_status: 'processing', processing_stage: 'ocr', processing_progress: 42 },
        }],
      },
      global: { stubs: { IcIcon: true } },
    })

    const card = wrapper.get('.attachment-card')
    expect(card.text()).toContain('OCR')
    expect(card.get('.attachment-progress-track > span').attributes('style')).toContain('42%')
    expect(wrapper.find('.attachment-drop-overlay').exists()).toBe(false)
  })
})
