/**
 * 文件树整体替换的浏览器冒烟测试。
 * 使用真实页面和模拟知识库接口，验证递归结构、展开动效、层级线与行交互。
 */
import { expect, test } from '@playwright/test'

/** 为文件工作区提供稳定且完整的最小接口响应。 */
test.beforeEach(async ({ page }) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    const responses: Record<string, unknown> = {
      '/health': 'ok',
      '/settings/models/status': { embedding: 'ready', rerank: 'ready' },
      '/settings/profile': {
        user_id: 'file-tree-e2e-user',
        knowledge_dir: 'D:/Knowledge',
        active_library_id: 'default',
        knowledge_libraries: [],
      },
      '/knowledge/files': {
        tree: [
          {
            name: 'src',
            path: 'src',
            isDir: true,
            children: [
              {
                name: 'app',
                path: 'src/app',
                isDir: true,
                children: [{
                  name: 'page.tsx',
                  path: 'src/app/page.tsx',
                  isDir: false,
                  size: 128,
                  indexStatus: 'indexed',
                  graphStatus: 'graphed',
                }],
              },
            ],
          },
        ],
      },
      '/favorites': { favorites: [] },
      '/knowledge/trash': { entries: [] },
      '/sessions': [],
      '/sessions/observability/history': [],
      '/agent/token-usage': { interval: '5m', calls: [], buckets: [], sessions: [] },
      '/skills': { skills: [], count: 0 },
      '/todo/list': [],
      '/automation/list': [],
      '/library/items': { items: [] },
      '/git/status': {
        initialized: false,
        branches: [],
        remote_branches: [],
        remotes: [],
        changes: [],
        untracked: [],
        ignored: [],
      },
    }

    if (pathname in responses) {
      const body = responses[pathname]
      await route.fulfill({
        status: 200,
        contentType: typeof body === 'string' ? 'text/plain' : 'application/json',
        body: typeof body === 'string' ? body : JSON.stringify(body),
      })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'file-tree-e2e-user',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
    localStorage.setItem('agent_editor_show_index_column', 'true')
    localStorage.setItem('agent_editor_show_graph_column', 'true')
    localStorage.setItem('agent_editor_show_favorite_column', 'true')
  })
})

test('uses the provided checkbox tree component throughout the file tree', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: '进入文件', exact: true }).click()

  const tree = page.locator('.tree-root')
  const srcToggle = tree.locator('.tree-toggle').first()
  const srcLabel = tree.locator('.tree-label').filter({ hasText: 'src' }).first()
  const srcIcon = srcLabel.locator('.material-file-icon')
  await expect(tree).toBeVisible()
  await expect(srcToggle).not.toBeChecked()
  await expect(srcIcon).toBeVisible()
  const closedFolderIcon = await srcIcon.getAttribute('src')

  await srcLabel.click()
  await expect(srcToggle).toBeChecked()
  await expect.poll(() => srcIcon.getAttribute('src')).not.toBe(closedFolderIcon)
  await expect(tree.locator('.tree-label').filter({ hasText: 'app' })).toBeVisible()

  const nestedList = tree.locator('.tree-children').first()
  await expect(nestedList).toHaveCSS('border-left-width', '1px')
  await expect(nestedList).toHaveCSS('padding-left', '11px')
  await expect(tree.locator('.tree-children-wrapper').first()).toHaveCSS(
    'transition-duration',
    '0.3s',
  )

  const appLabel = tree.locator('.tree-label').filter({ hasText: 'app' })
  await appLabel.click()
  const fileRow = tree.locator('.file-item').filter({ hasText: 'page.tsx' })
  await expect(fileRow).toBeVisible()
  await expect(fileRow.locator('.material-file-icon')).toBeVisible()
  await expect(fileRow.locator('.node-index-dot.indexed')).toBeVisible()
  await expect(fileRow.locator('.node-graph-dot.graphed')).toBeVisible()
  await expect(fileRow.locator('.favorite-button')).toBeVisible()
  const visibleStatusNameWidth = await fileRow.locator('.tree-name').evaluate(
    (element) => element.getBoundingClientRect().width,
  )

  await page.locator('.header-action[title="隐藏索引、图谱与收藏状态"]').click()
  await expect(fileRow.locator('.node-status-cluster')).toHaveCount(0)
  await expect(fileRow.locator('.favorite-button')).toHaveCount(0)
  const hiddenStatusNameWidth = await fileRow.locator('.tree-name').evaluate(
    (element) => element.getBoundingClientRect().width,
  )
  expect(hiddenStatusNameWidth).toBeGreaterThan(visibleStatusNameWidth)
  await fileRow.click()
  await expect(fileRow).toHaveClass(/is-selected/)
  await fileRow.hover()

  await tree.screenshot({ path: testInfo.outputPath('file-tree-replacement.png') })
})
