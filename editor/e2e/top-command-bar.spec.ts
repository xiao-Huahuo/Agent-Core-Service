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

test('wraps the Agent sidebar in the workspace card shell', async ({ page }) => {
  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  if (await userIdInput.isVisible()) {
    await userIdInput.fill('agent-card-smoke')
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }

  await page.getByTitle('切换 Agent 面板').click()
  const agentCard = page.locator('.agent-col')
  const agentPanel = agentCard.locator('.agent-panel')
  const workspaceCard = page.locator('.main-shell.ide-panel')
  await expect(agentCard).toBeVisible()
  await expect.poll(async () => {
    const [agentRadius, workspaceRadius] = await Promise.all([
      agentCard.evaluate((element) => getComputedStyle(element).borderRadius),
      workspaceCard.evaluate((element) => getComputedStyle(element).borderRadius),
    ])
    return agentRadius === workspaceRadius
  }).toBe(true)
  await expect(agentCard).toHaveCSS('overflow', 'hidden')
  await expect(agentCard).toHaveCSS('border-top-width', '0px')
  await expect(workspaceCard).toHaveCSS('border-top-width', '0px')
  await expect(agentCard).toHaveCSS('box-shadow', /4px/)
  await expect(workspaceCard).toHaveCSS('box-shadow', /4px/)
  await expect(agentCard).toHaveCSS('margin-left', '12px')
  await expect(agentCard).toHaveCSS('margin-right', '12px')
  await expect(agentCard).toHaveCSS('margin-top', '12px')
  await expect(agentCard).toHaveCSS('margin-bottom', '12px')
  await expect(workspaceCard).toHaveCSS('margin-left', '12px')
  await expect(workspaceCard).toHaveCSS('margin-right', '12px')
  await expect(workspaceCard).toHaveCSS('margin-top', '12px')
  await expect(workspaceCard).toHaveCSS('margin-bottom', '12px')
  await expect.poll(async () => {
    const [agentBackground, workspaceBackground] = await Promise.all([
      agentPanel.evaluate((element) => getComputedStyle(element).backgroundColor),
      workspaceCard.evaluate((element) => getComputedStyle(element).backgroundColor),
    ])
    return agentBackground === workspaceBackground
  }).toBe(true)
})

test('resizes the sidebar browser from its left edge', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  if (await userIdInput.isVisible()) {
    await userIdInput.fill('browser-resize-smoke')
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }

  await page.getByRole('button', { name: '打开或收起右侧浏览器' }).click()
  const browserSidebar = page.locator('.browser-sidebar-content')
  await expect(browserSidebar).toBeVisible()
  const browserWidthBefore = (await browserSidebar.boundingBox())?.width ?? 0
  const browserResizer = page.getByRole('separator', { name: 'Resize browser sidebar' })
  await expect(browserResizer).toBeVisible()
  const browserHandleBox = await browserResizer.boundingBox()
  await page.mouse.move(
    (browserHandleBox?.x ?? 0) + (browserHandleBox?.width ?? 4) / 2,
    (browserHandleBox?.y ?? 0) + (browserHandleBox?.height ?? 400) / 2,
  )
  await page.mouse.down()
  await page.mouse.move((browserHandleBox?.x ?? 0) - 80, (browserHandleBox?.y ?? 0) + (browserHandleBox?.height ?? 400) / 2)
  await page.mouse.up()

  await expect.poll(async () => (await browserSidebar.boundingBox())?.width ?? 0).toBeGreaterThan(browserWidthBefore + 60)
  await page.screenshot({ path: testInfo.outputPath('browser-sidebar-resized.png'), fullPage: true })
})

test('keeps the library name visible beside ingestion progress', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: '1',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'knowledge-library',
      knowledgeLibraries: [{
        libraryId: 'knowledge-library',
        name: 'knowledge',
        knowledgeDir: 'D:/Knowledge',
        libraryStorageDir: '.metaweave/library',
        isActive: true,
      }],
    }))
  })
  await page.goto('/')

  const libraryName = page.locator('.library-name-input')
  await expect(libraryName).toBeVisible()
  await libraryName.evaluate((element) => {
    const input = element as HTMLInputElement
    input.value = 'knowledge'
    input.dispatchEvent(new Event('input', { bubbles: true }))

    const brand = input.closest<HTMLElement>('.brand')
    if (brand) {
      brand.style.width = '230px'
      brand.style.maxWidth = '230px'
      brand.style.flexBasis = '230px'
    }
    const progress = document.createElement('div')
    progress.className = 'ingestion-progress'
    progress.style.flex = '0 0 140px'
    progress.style.width = '140px'
    progress.innerHTML = '<span class="ingestion-progress-track"></span><span class="ingestion-progress-percent">33%</span>'
    brand?.append(progress)
  })

  await expect.poll(async () => libraryName.evaluate((element) => {
    const input = element as HTMLInputElement
    return input.clientWidth >= input.scrollWidth
  })).toBe(true)
})
