/*
 * Multimodal preview component tests.
 *
 * Usage:
 * Verifies browser-native media viewers receive the backend raw-file source.
 */

import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MultimodalPreview from '../MultimodalPreview.vue'

const attachMediaElement = vi.fn()
const load = vi.fn()
const unload = vi.fn()
const detachMediaElement = vi.fn()
const destroy = vi.fn()

vi.mock('mpegts.js', () => ({
  default: {
    isSupported: () => true,
    createPlayer: vi.fn(() => ({
      attachMediaElement,
      load,
      unload,
      detachMediaElement,
      destroy,
    })),
  },
}))

describe('MultimodalPreview video modality', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

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

  it('transmuxes MPEG-TS content whose filename incorrectly ends in mp4', async () => {
    const wrapper = mount(MultimodalPreview, {
      props: {
        preview: {
          path: 'media/recording.mp4',
          kind: 'video',
          video_container: 'mpegts',
          raw_url: '/knowledge/files/raw?user_id=u1&path=media%2Frecording.mp4',
          mime_type: 'video/mp4',
          mtime: '2026-08-20 12:00',
          size: 269_672_088,
          extension: '.mp4',
          readonly: true,
        },
      },
    })

    await wrapper.vm.$nextTick()

    expect(attachMediaElement).toHaveBeenCalledWith(wrapper.get('video').element)
    expect(load).toHaveBeenCalledOnce()

    wrapper.unmount()
    expect(unload).toHaveBeenCalledOnce()
    expect(detachMediaElement).toHaveBeenCalledOnce()
    expect(destroy).toHaveBeenCalledOnce()
  })
})
