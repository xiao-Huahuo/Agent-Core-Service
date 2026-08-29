import { describe, it, expect } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../App.vue'
import router from '../router'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('App', () => {
  it('mounts renders properly', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia(), router],
      },
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('never waits for models before showing the application shell', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/App.vue'), 'utf8')

    expect(source).not.toContain('waitForModelsReady')
    expect(source).toContain('initializeManagedModels')
    expect(source).toContain('<ModelLifecycleOverlay')
  })
})
