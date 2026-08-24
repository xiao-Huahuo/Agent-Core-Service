/** Appearance settings UI tests for independent font-size controls. */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppearanceSettingsSection from '@/components/settings_view/AppearanceSettingsSection.vue'

describe('AppearanceSettingsSection font sizes', () => {
  it('renders separate UI and editor text font-size controls', () => {
    const wrapper = mount(AppearanceSettingsSection, {
      props: {
        uiFontFamiliesDraft: [],
        textFontFamiliesDraft: [],
        uiFontSizePercentDraft: 90,
        textFontSizePercentDraft: 125,
        themePrimaryColorDraft: '#339cff',
        themeSoftColorDraft: '#339cff',
        themeOptions: [{ value: 'light', label: '亮色' }],
        themeMode: 'light',
        sidebarDisplayMode: 'icons',
        availableFontFamilies: [],
        fontsLoading: false,
        showBacklinks: false,
        userId: 'u1',
        backgroundCoverUrl: '/library/assets/u1/cover.png',
      },
      global: { stubs: { LibraryCoverUploader: { template: '<div class="cover-uploader-stub" />' } } },
    })

    expect(wrapper.text()).toContain('UI 字体大小')
    expect(wrapper.text()).toContain('正文字体大小')
    expect(wrapper.find('[data-font-size="ui"]').exists()).toBe(true)
    expect(wrapper.find('[data-font-size="text"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('显示反向链接')
    expect(wrapper.text()).toContain('背景封面图片')
    expect(wrapper.find('.cover-uploader-stub').exists()).toBe(true)
    expect(wrapper.get('button[aria-label="重置背景封面"]')).toBeTruthy()
    expect(wrapper.find('#show-backlinks-setting').attributes('checked')).toBeUndefined()
  })
})
