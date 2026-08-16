/** Component preview compiler tests. */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ComponentPreview from '@/components/component_library/ComponentPreview.vue'
import {
  buildComponentPreviewDocument,
  COMPONENT_PREVIEW_SIZE_MESSAGE,
} from '@/components/component_library/componentPreview'

describe('component preview compiler', () => {
  it('compiles an interactive Vue SFC into an offline sandbox document', () => {
    const source = `
      <script setup>
      import { ref } from 'vue'
      const count = ref(0)
      </script>
      <template><button @click="count += 1">{{ count }}</button></template>
      <style scoped>button { color: red; }</style>
    `

    const document = buildComponentPreviewDocument(source, 'vue')

    expect(document).toContain("connect-src 'none'")
    expect(document).toContain('Vue.createApp')
    expect(document).toContain('const { ref } = Vue')
    expect(document).toContain('metaweave-component-preview-size')
    expect(document).toContain('ResizeObserver')
    expect(document).not.toMatch(/import\s+\{\s*ref/)
  })

  it('keeps standalone HTML interactive inside the same restrictive policy', () => {
    const document = buildComponentPreviewDocument(
      '<button onclick="this.textContent=\'Done\'">Click</button>',
      'html',
    )

    expect(document).toContain("default-src 'none'")
    expect(document).toContain('onclick="this.textContent=\'Done\'"')
  })

  it('rejects imports that would require undeclared external dependencies', () => {
    expect(() => buildComponentPreviewDocument(
      '<script setup>import anime from \'animejs\'</script><template><div /></template>',
      'vue',
    )).toThrow('Only imports from vue are supported')
  })

  it('ignores viewport-coupled height reports that would grow a card forever', () => {
    const wrapper = mount(ComponentPreview, {
      props: {
        source: '<button>Stable</button>',
        sourceFormat: 'html',
        label: '稳定组件',
      },
      attachTo: document.body,
    })
    const frame = wrapper.get('iframe').element as HTMLIFrameElement
    Object.defineProperty(frame, 'clientHeight', { configurable: true, value: 280 })

    window.dispatchEvent(new MessageEvent('message', {
      source: frame.contentWindow,
      data: { type: COMPONENT_PREVIEW_SIZE_MESSAGE, width: 240, height: 280 },
    }))
    expect(wrapper.emitted('resize')).toBeUndefined()

    window.dispatchEvent(new MessageEvent('message', {
      source: frame.contentWindow,
      data: { type: COMPONENT_PREVIEW_SIZE_MESSAGE, width: 120, height: 64 },
    }))
    expect(wrapper.emitted('resize')).toEqual([[{ width: 120, height: 64 }]])
    wrapper.unmount()
  })
})
