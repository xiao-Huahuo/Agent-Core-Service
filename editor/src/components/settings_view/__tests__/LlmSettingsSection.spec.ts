/**
 * LLM settings effective-model summary tests.
 *
 * Usage:
 * Verifies that users can distinguish local fallback, large-model reuse, and
 * separately configured large/small model routing from the real saved state.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LlmSettingsSection from '../LlmSettingsSection.vue'

function mountSection(overrides: Record<string, unknown> = {}) {
  return mount(LlmSettingsSection, {
    props: {
      largeModelName: '',
      largeBaseUrl: '',
      largeApiKey: '',
      largeContextWindowTokens: 1_000_000,
      largeMaxOutputTokens: 0,
      smallModelName: '',
      smallBaseUrl: '',
      smallApiKey: '',
      smallContextWindowTokens: 1_000_000,
      smallMaxOutputTokens: 0,
      showLargeKey: false,
      showSmallKey: false,
      modelEditing: false,
      modelConfigSaved: false,
      modelSaving: false,
      modelMsg: '',
      savedConfigs: [],
      modelConfigLoaded: true,
      effectiveLargeModelName: 'Qwen/Qwen3.5-2B',
      effectiveLargeModelSource: 'local',
      effectiveSmallModelName: 'Qwen/Qwen3.5-2B',
      effectiveSmallModelSource: 'local',
      savedSmallModelConfigured: false,
      ...overrides,
    },
  })
}

describe('LLM effective model summary', () => {
  it('shows the local model for both roles when no remote large model is configured', () => {
    const wrapper = mountSection()

    expect(wrapper.get('[data-effective-model="large"]').text()).toContain('Qwen/Qwen3.5-2B')
    expect(wrapper.get('[data-effective-model="large"]').text()).toContain('本地回退')
    expect(wrapper.get('[data-effective-model="small"]').text()).toContain('本地回退')
  })

  it('shows that the small role reuses the configured large model', () => {
    const wrapper = mountSection({
      effectiveLargeModelName: 'remote-large',
      effectiveLargeModelSource: 'remote',
      effectiveSmallModelName: 'remote-large',
      effectiveSmallModelSource: 'remote',
    })

    expect(wrapper.get('[data-effective-model="large"]').text()).toContain('远程配置')
    expect(wrapper.get('[data-effective-model="small"]').text()).toContain('复用大模型')
  })

  it('shows separately configured large and small models', () => {
    const wrapper = mountSection({
      effectiveLargeModelName: 'remote-large',
      effectiveLargeModelSource: 'remote',
      effectiveSmallModelName: 'remote-small',
      effectiveSmallModelSource: 'remote',
      savedSmallModelConfigured: true,
    })

    expect(wrapper.get('[data-effective-model="large"]').text()).toContain('remote-large')
    expect(wrapper.get('[data-effective-model="small"]').text()).toContain('remote-small')
    expect(wrapper.get('[data-effective-model="small"]').text()).toContain('独立配置')
  })

  it('resets cleared model capacity to the one-million service default', async () => {
    const wrapper = mountSection({
      modelEditing: true,
      largeContextWindowTokens: 500_000,
      smallContextWindowTokens: 200_000,
    })

    await wrapper.get('button[aria-label="清空大模型配置"]').trigger('click')
    await wrapper.get('button[aria-label="清空小模型配置"]').trigger('click')

    expect(wrapper.emitted('update:largeContextWindowTokens')?.at(-1)).toEqual([1_000_000])
    expect(wrapper.emitted('update:smallContextWindowTokens')?.at(-1)).toEqual([1_000_000])
  })
})
