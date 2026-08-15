/*
 * Chat store development-runtime contract.
 *
 * Usage:
 * Prevents a Vite update from leaving an already-created Pinia chat store on
 * the previous send() closure while newly mounted components use new code.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('chat store hot-update contract', () => {
  it('registers the primary store with Pinia HMR', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/stores/chat.ts'), 'utf8')

    expect(source).toContain("import { acceptHMRUpdate, defineStore } from 'pinia'")
    expect(source).toContain('import.meta.hot.accept(acceptHMRUpdate(useChatStore, import.meta.hot))')
  })
})
