/** Guards the literature-reading async page against invalid Reka UI exports. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/views/LiteratureReadingView.vue'), 'utf8')

describe('LiteratureReadingView module', () => {
  it('aliases the exported Reka dropdown root to the template component name', () => {
    expect(source).toContain('DropdownMenuRoot as DropdownMenu')
    expect(source).not.toMatch(/\n\s*DropdownMenu,\n/)
  })
})
