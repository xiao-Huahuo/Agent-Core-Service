/*
 * Model lifecycle overlay tests.
 *
 * Usage:
 * Uses mocked backend DTOs only; no real model files, downloads, or loaders are touched.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ModelLifecycleOverlay from '../ModelLifecycleOverlay.vue'

const { fetchModelManagement, downloadManagedModel } = vi.hoisted(() => ({
  fetchModelManagement: vi.fn(),
  downloadManagedModel: vi.fn().mockResolvedValue({ status: 'started', model: 'embedding' }),
}))

vi.mock('@/api/settings', () => ({ fetchModelManagement, downloadManagedModel }))

function model(key: string, status: string) {
  return {
    key,
    label: key === 'embedding' ? 'Embedding 模型' : 'ReRank 模型',
    role: 'test',
    name: `demo/${key}`,
    path: `D:/models/${key}`,
    base_path: 'D:/models',
    size_bytes: 0,
    file_count: 0,
    status,
    enabled: true,
    active: false,
    downloaded: false,
    progress: {
      status: status === 'downloading' ? 'downloading' : 'idle',
      stage: '',
      downloaded_bytes: 64,
      total_bytes: 256,
      percent: 25,
      indeterminate: false,
      message: '',
    },
    details: {},
  }
}

describe('ModelLifecycleOverlay', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.clearAllMocks()
  })

  it('renders independent notices and confirms only the selected model download', async () => {
    fetchModelManagement.mockResolvedValue({
      models: [model('embedding', 'awaiting_download'), model('rerank', 'downloading')],
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const wrapper = mount(ModelLifecycleOverlay, { props: { userId: 'u1' } })
    await flushPromises()

    expect(wrapper.findAll('.model-lifecycle-notice')).toHaveLength(2)
    expect(wrapper.text()).toContain('Embedding模型未下载')
    expect(wrapper.text()).toContain('正在下载ReRank模型')
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(downloadManagedModel).toHaveBeenCalledWith('embedding', 'u1')
    wrapper.unmount()
  })
})
