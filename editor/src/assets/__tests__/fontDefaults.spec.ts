/** Verifies that the bundled primary UI/text font remains wired into global styles. */

import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const assetsDirectory = resolve(process.cwd(), 'src/assets')

describe('global font defaults', () => {
  it('bundles HYWenHei-85W and uses it first for UI and text', () => {
    const mainCss = readFileSync(`${assetsDirectory}/main.css`, 'utf8')
    const uiSystemCss = readFileSync(`${assetsDirectory}/ui-system.css`, 'utf8')

    expect(existsSync(`${assetsDirectory}/fonts/HYWenHei-85W.otf`)).toBe(true)
    expect(mainCss).toMatch(/font-family:\s*"HYWenHei-85W"[\s\S]*HYWenHei-85W\.otf/)
    expect(uiSystemCss).toMatch(/--font-ui-default:\s*"HYWenHei-85W",/)
    expect(uiSystemCss).toMatch(/--font-text-default:\s*"HYWenHei-85W",/)
  })
})
