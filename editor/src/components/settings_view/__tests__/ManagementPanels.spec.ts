/*
 * Model and compiler management component tests.
 *
 * Usage:
 * Verifies backend-owned details, real byte progress, expandable information,
 * and friendly compiler lifecycle actions render without fabricated values.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CompilerManagement from '../CompilerManagement.vue'
import ModelManagement from '../ModelManagement.vue'

const {
  fetchModelManagement,
  checkModelDisk,
  downloadManagedModel,
  loadManagedModel,
  fetchLatexManagement,
  installLatexRuntime,
  cancelLatexInstall,
  uninstallLatexRuntime,
} = vi.hoisted(() => ({
  fetchModelManagement: vi.fn(),
  checkModelDisk: vi.fn().mockResolvedValue({}),
  downloadManagedModel: vi.fn().mockResolvedValue({ status: 'started', model: 'embedding' }),
  loadManagedModel: vi.fn().mockResolvedValue({ status: 'triggered', model: 'rerank' }),
  fetchLatexManagement: vi.fn(),
  installLatexRuntime: vi.fn(),
  cancelLatexInstall: vi.fn(),
  uninstallLatexRuntime: vi.fn(),
}))

vi.mock('@/api/settings', () => ({
  fetchModelManagement,
  checkModelDisk,
  downloadManagedModel,
  loadManagedModel,
}))

vi.mock('@/api/latex', () => ({
  fetchLatexManagement,
  installLatexRuntime,
  cancelLatexInstall,
  uninstallLatexRuntime,
}))

const iconStub = { template: '<span class="icon-stub"></span>' }

describe('management panels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    checkModelDisk.mockResolvedValue({})
  })

  it('shows real model bytes, enabled state and expandable backend details', async () => {
    fetchModelManagement.mockResolvedValue({ models: [{
      key: 'embedding',
      label: 'Embedding 模型',
      role: '知识向量化',
      name: 'BAAI/demo',
      path: 'D:/models/demo',
      base_path: 'D:/models',
      size_bytes: 1024,
      file_count: 4,
      status: 'downloading',
      enabled: true,
      active: false,
      downloaded: false,
      progress: {
        status: 'downloading', stage: 'model_files', downloaded_bytes: 50,
        total_bytes: 200, percent: 25, indeterminate: false, message: '正在下载模型文件',
      },
      details: { provider: 'Hugging Face', repository: 'BAAI/demo' },
    }] })
    const wrapper = mount(ModelManagement, {
      props: { userId: 'u1' },
      global: { stubs: { IcIcon: iconStub } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('已启用')
    expect(wrapper.text()).toMatch(/50 B\s+\/ 200 B · 25%/u)
    expect(wrapper.get('progress').attributes('value')).toBe('25')
    await wrapper.get('.details-toggle').trigger('click')
    expect(wrapper.text()).toContain('D:/models/demo')
    expect(wrapper.text()).toContain('Hugging Face')
  })

  it('polls automatically when an active download is discovered on initial load', async () => {
    vi.useFakeTimers()
    const downloadingModel = (percent: number) => ({
      key: 'local_qwen',
      label: '本地 Qwen 大语言模型',
      role: '本地主 Agent、小模型回退与图片理解',
      name: 'Qwen/Qwen3.5-2B',
      path: 'D:/models/qwen',
      base_path: 'D:/models',
      size_bytes: percent,
      file_count: 4,
      status: 'downloading',
      enabled: true,
      active: false,
      downloaded: false,
      progress: {
        status: 'downloading', stage: 'model_files', downloaded_bytes: percent,
        total_bytes: 100, percent, indeterminate: false, message: '正在下载模型文件',
      },
      details: { provider: 'Hugging Face' },
    })
    fetchModelManagement
      .mockResolvedValueOnce({ models: [downloadingModel(25)] })
      .mockResolvedValueOnce({ models: [downloadingModel(50)] })

    const wrapper = mount(ModelManagement, {
      props: { userId: 'u1' },
      global: { stubs: { IcIcon: iconStub } },
    })
    await flushPromises()
    expect(wrapper.get('progress').attributes('value')).toBe('25')

    await vi.advanceTimersByTimeAsync(750)
    await flushPromises()

    expect(fetchModelManagement).toHaveBeenCalledTimes(2)
    expect(wrapper.get('progress').attributes('value')).toBe('50')
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('shows compiler source, location, size, engines and honest unknown progress', async () => {
    fetchLatexManagement.mockResolvedValue({
      status: 'installing', stage: 'packages', progress: null, message: '正在下载 MiKTeX basic 宏包',
      downloaded_bytes: 4096, total_bytes: null, indeterminate: true,
      source: 'managed', managed: true, distribution: 'MiKTeX', version: 'MiKTeX 25.12',
      compiler_path: 'D:/runtime/miktex/pdflatex.exe', latexmk_path: 'D:/runtime/miktex/latexmk.exe',
      default_engine: 'pdflatex', runtime_path: 'D:/runtime/latex', distribution_path: 'D:/runtime/miktex',
      size_bytes: 8192, file_count: 20,
      engines: [
        { name: 'pdflatex', available: true, path: 'D:/runtime/miktex/pdflatex.exe', default: true },
        { name: 'xelatex', available: true, path: 'D:/runtime/miktex/xelatex.exe', default: false },
      ],
      paths: { repository: 'D:/runtime/repository' },
    })
    const wrapper = mount(CompilerManagement, {
      props: { userId: 'u1' },
      global: { stubs: { IcIcon: iconStub } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('MetaWeave 托管')
    expect(wrapper.text()).toContain('4.0 KB')
    expect(wrapper.get('progress').attributes('value')).toBeUndefined()
    await wrapper.get('.details-toggle').trigger('click')
    expect(wrapper.text()).toContain('D:/runtime/miktex')
    expect(wrapper.text()).toContain('pdflatex')
    expect(wrapper.text()).toContain('xelatex')
  })
})
