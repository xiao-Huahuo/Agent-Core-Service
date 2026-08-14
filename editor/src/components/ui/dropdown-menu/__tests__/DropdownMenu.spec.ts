/*
 * Shared dropdown-menu interaction test.
 * Verifies that the themed radio items preserve Reka UI selection semantics.
 */
import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '..'
import contentSource from '../DropdownMenuContent.vue?raw'
import radioItemSource from '../DropdownMenuRadioItem.vue?raw'

const TestMenu = defineComponent({
  components: {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuRadioGroup,
    DropdownMenuRadioItem,
    DropdownMenuTrigger,
  },
  setup() {
    return { selection: ref('books') }
  },
  template: `
    <DropdownMenu :open="true">
      <DropdownMenuTrigger>筛选</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuRadioGroup v-model="selection">
          <DropdownMenuRadioItem value="books">图书</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="collections">集锦</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  `,
})

describe('DropdownMenu', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('updates the checked radio item', async () => {
    mount(TestMenu, { attachTo: document.body })
    await nextTick()

    const items = [...document.querySelectorAll<HTMLElement>('[role="menuitemradio"]')]
    expect(items).toHaveLength(2)
    expect(items[0]?.dataset.state).toBe('checked')

    items[1]?.click()
    await nextTick()

    expect(items[1]?.dataset.state).toBe('checked')
  })

  it('keeps styles global for Reka primitive output', () => {
    expect(contentSource).toContain('<style>')
    expect(contentSource).not.toContain('<style scoped>')
    expect(contentSource).toContain(".ui-dropdown-content[data-state='open']")
    expect(contentSource).toContain('animation: dropdown-in 160ms')
    expect(contentSource).toContain(".ui-dropdown-content[data-state='closed']")
    expect(contentSource).toContain('animation: dropdown-out 120ms')
    expect(radioItemSource).toContain('<style>')
    expect(radioItemSource).not.toContain('<style scoped>')
  })
})
