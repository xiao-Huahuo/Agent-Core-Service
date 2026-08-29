/** Browser smoke test for the bundled primary UI and text font. */

import { expect, test } from '@playwright/test'

test('loads HYWenHei-85W as the primary UI and text font', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => document.fonts.ready)

  const fontState = await page.evaluate(() => ({
    bodyFamily: getComputedStyle(document.body).fontFamily,
    textDefault: getComputedStyle(document.documentElement).getPropertyValue('--font-text-default'),
    uiDefault: getComputedStyle(document.documentElement).getPropertyValue('--font-ui-default'),
    loaded: document.fonts.check('16px "HYWenHei-85W"', '原神 MetaWeave'),
  }))

  expect(fontState.loaded).toBe(true)
  expect(fontState.bodyFamily.startsWith('HYWenHei-85W')).toBe(true)
  expect(fontState.uiDefault.trim().startsWith('"HYWenHei-85W"')).toBe(true)
  expect(fontState.textDefault.trim().startsWith('"HYWenHei-85W"')).toBe(true)
})
