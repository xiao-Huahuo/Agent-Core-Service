/**
 * Top command bar browser regression checks.
 *
 * Usage:
 * Verifies that the collapsed toolbar search only reserves its visible icon
 * width, leaving the former expansion area on the draggable top bar.
 */
import { expect, test } from '@playwright/test'

test('collapsed toolbar search releases its expansion area for window dragging', async ({ page }) => {
  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  if (await userIdInput.isVisible()) {
    await userIdInput.fill('topbar-smoke')
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }

  const searchCenter = page.locator('.search-center')
  await expect(searchCenter).toBeVisible()
  await expect.poll(async () => (await searchCenter.boundingBox())?.width ?? 0).toBeLessThanOrEqual(27)

  const collapsedBox = await searchCenter.boundingBox()
  const releasedPoint = await page.evaluate(({ x, y }) => {
    const target = document.elementFromPoint(x, y)
    return {
      topbar: Boolean(target?.closest('.topbar')),
      actions: Boolean(target?.closest('.actions')),
    }
  }, {
    x: Math.max(1, (collapsedBox?.x ?? 40) - 24),
    y: (collapsedBox?.y ?? 0) + (collapsedBox?.height ?? 26) / 2,
  })
  expect(releasedPoint).toEqual({ topbar: true, actions: false })

  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect.poll(async () => (await searchCenter.boundingBox())?.width ?? 0).toBeGreaterThanOrEqual(249)
})
