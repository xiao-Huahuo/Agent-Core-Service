import { beforeEach, describe, expect, it, vi } from 'vitest'

import { mount } from '@vue/test-utils'

import VditorEditor from '../VditorEditor.vue'

const vditorMocks = vi.hoisted(() => {
  const undo = vi.fn()
  const redo = vi.fn()
  const instance = {
    vditor: {
      undo: { undo, redo },
    },
    disabledCache: vi.fn(),
    clearCache: vi.fn(),
    getValue: vi.fn(() => 'initial value'),
    setValue: vi.fn(),
    destroy: vi.fn(),
  }

  const constructor = vi.fn(function VditorMock() {
    return instance
  })

  return {
    undo,
    redo,
    instance,
    constructor,
  }
})

vi.mock('vditor', () => ({ default: vditorMocks.constructor }))

function mountEditor() {
  return mount(VditorEditor, {
    props: {
      modelValue: 'initial value',
      toolbarVisible: false,
    },
  })
}

function dispatchShortcut(element: Element, init: KeyboardEventInit) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    ...init,
  })
  element.dispatchEvent(event)
  return event
}

describe('VditorEditor history shortcuts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uses the Vditor undo stack for Ctrl+Z', () => {
    const wrapper = mountEditor()
    const event = dispatchShortcut(wrapper.get('.vditor-host').element, {
      key: 'z',
      ctrlKey: true,
    })

    expect(vditorMocks.undo).toHaveBeenCalledExactlyOnceWith(vditorMocks.instance.vditor)
    expect(vditorMocks.redo).not.toHaveBeenCalled()
    expect(event.defaultPrevented).toBe(true)
  })

  it.each([
    ['Ctrl+Y', { key: 'y', ctrlKey: true }],
    ['Ctrl+Shift+Z', { key: 'z', ctrlKey: true, shiftKey: true }],
  ])('uses the Vditor redo stack for %s', (_label, shortcut) => {
    const wrapper = mountEditor()
    const event = dispatchShortcut(wrapper.get('.vditor-host').element, shortcut)

    expect(vditorMocks.redo).toHaveBeenCalledExactlyOnceWith(vditorMocks.instance.vditor)
    expect(vditorMocks.undo).not.toHaveBeenCalled()
    expect(event.defaultPrevented).toBe(true)
  })
})
