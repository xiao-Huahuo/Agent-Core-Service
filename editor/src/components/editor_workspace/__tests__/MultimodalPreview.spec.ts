/*
 * Multimodal preview component tests.
 *
 * Usage:
 * Verifies browser-native media viewers receive the backend raw-file source.
 */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MultimodalPreview from '../MultimodalPreview.vue'

describe('MultimodalPreview video modality', () => {
  it('renders an embedded video player with native controls', () => {
    const wrapper = mount(MultimodalPreview, {
      props: {
        preview: {
          path: 'media/clip.mp4',
          kind: 'video',
          raw_url: '/knowledge/files/raw?user_id=u1&path=media%2Fclip.mp4',
          mime_type: 'video/mp4',
          mtime: '2026-08-20 12:00',
          size: 5,
          extension: '.mp4',
          readonly: true,
        },
      },
    })

    const player = wrapper.get('video.video-preview')
    expect(player.attributes('controls')).toBeDefined()
    expect(player.attributes('preload')).toBe('metadata')
    expect(player.get('source').attributes('src')).toContain('/knowledge/files/raw')
    expect(player.get('source').attributes('type')).toBe('video/mp4')
  })
})
