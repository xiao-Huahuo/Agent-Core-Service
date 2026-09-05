/**
 * 顶栏品牌区响应式浏览器冒烟。
 *
 * 用途：验证左上角使用放大的彩色 Logo 和 Agent 标题图，并确保桌面与
 * 移动宽度均不回退为知识库文字或溢出顶栏。
 */
import { expect, test } from '@playwright/test'

test('shows the color logo and hides the title artwork at mobile width', async ({ page }) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname === '/settings/profile') {
      await route.fulfill({ json: { user_id: 'e2e-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [] } })
      return
    }
    if (pathname === '/knowledge/files/events') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    const responses: Record<string, unknown> = {
      '/sessions': [],
      '/favorites': { favorites: [] },
      '/privacy': { privacy: [] },
      '/knowledge/files': { tree: [] },
      '/todo/list': [],
      '/automation/list': [],
      '/settings/models/status': {},
      '/settings/models/management': { models: [] },
    }
    if (pathname in responses) {
      await route.fulfill({ json: responses[pathname] })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ json: {} })
      return
    }
    await route.continue()
  })
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_theme_mode', 'light')
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'e2e-user', knowledgeDir: 'D:/Knowledge', knowledgeLibraries: [],
    }))
  })

  for (const viewport of [
    { name: 'desktop', width: 1280, height: 800 },
    { name: 'mobile', width: 480, height: 800 },
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    // Mocked requests settle deterministically before responsive geometry checks.
    // eslint-disable-next-line playwright/no-networkidle
    await page.waitForLoadState('networkidle')
    const logo = page.locator('.topbar .logo-img')
    const title = page.locator('.topbar .brand-title')
    await expect(logo).toBeVisible()
    await expect(page.locator('.topbar .library-name-text')).toHaveCount(0)
    expect(await logo.evaluate((element) => getComputedStyle(element).filter)).toBe('none')
    const logoBox = await logo.boundingBox()
    expect(logoBox?.width).toBeGreaterThanOrEqual(58)
    if (viewport.name === 'mobile') {
      await expect(title).toBeHidden()
    } else {
      await expect(title).toBeVisible()
      const [titleBox, topbarBox] = await Promise.all([
        title.boundingBox(), page.locator('.topbar').boundingBox(),
      ])
      expect(titleBox?.width).toBeGreaterThan(120)
      expect(titleBox!.x + titleBox!.width).toBeLessThanOrEqual(topbarBox!.x + topbarBox!.width)
    }

    if (viewport.name === 'desktop') {
      await page.getByRole('button', { name: 'Agent', exact: true }).click()
      const agentPage = page.locator('.agent-panel.agent-page-mode:visible')
      await expect(agentPage).toBeVisible()
      const drawer = agentPage.locator('.session-drawer')
      if (!(await drawer.getAttribute('class'))?.split(/\s+/u).includes('open')) {
        await agentPage.getByTitle('Toggle sidebar').click()
      }
      await expect(drawer).toHaveClass(/open/u)
      const drawerLogo = drawer.locator('.brand-logo')
      const drawerTitle = drawer.locator('.brand-title')
      await expect(drawerLogo).toBeVisible()
      await expect(drawerTitle).toBeVisible()
      const activityBarBox = await page.locator('.activity-bar').boundingBox()
      await expect.poll(async () => (await drawerLogo.boundingBox())?.x ?? Number.NEGATIVE_INFINITY)
        .toBeGreaterThanOrEqual(activityBarBox!.x + activityBarBox!.width)
      const [drawerBox, drawerLogoBox, drawerTitleBox] = await Promise.all([
        drawer.boundingBox(), drawerLogo.boundingBox(), drawerTitle.boundingBox(),
      ])
      expect(drawerLogoBox?.width).toBeGreaterThanOrEqual(56)
      expect(drawerTitleBox?.width).toBeGreaterThan(120)
      expect(drawerTitleBox!.x).toBeGreaterThanOrEqual(drawerBox!.x)
      expect(drawerTitleBox!.x + drawerTitleBox!.width).toBeLessThanOrEqual(drawerBox!.x + drawerBox!.width)
      expect(drawerLogoBox!.x).toBeGreaterThanOrEqual(activityBarBox!.x + activityBarBox!.width)
    }
    await page.screenshot({ path: `../docs/acceptance/topbar-brand-${viewport.name}.png`, fullPage: false })
  }
})
