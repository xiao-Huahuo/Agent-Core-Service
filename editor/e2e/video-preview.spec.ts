/*
 * Video and Markdown HTML media browser smoke test.
 *
 * Usage:
 * Runs the real Vue/Vditor surfaces with mocked backend payloads and verifies
 * native video, HTML image, and iframe blocks are visible in Chromium.
 */

import { expect, test } from '@playwright/test'

const markdown = [
  '# HTML 媒体',
  '',
  '<img src="https://media.test/image.svg" alt="HTML 图片">',
  '',
  '<iframe src="https://media.test/embed" title="HTML 视频"></iframe>',
].join('\n')

test('shows the video modality and HTML media blocks', async ({ page }, testInfo) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.searchParams.get('path') ?? ''
    const json = (body: unknown) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
    if (url.hostname === 'media.test' && url.pathname === '/image.svg') return route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#4224EB"/><circle cx="320" cy="180" r="72" fill="#EB2463"/></svg>',
    })
    if (url.hostname === 'media.test' && url.pathname === '/embed') return route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<body style="margin:0;background:#09090b"><video controls style="width:100%;height:100%"></video></body>',
    })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'media-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [
        { name: 'clip.mp4', path: 'clip.mp4', isDir: false, size: 5 },
        { name: 'media.md', path: 'media.md', isDir: false, size: markdown.length },
      ],
    })
    if (url.pathname === '/knowledge/files/preview') return json({
      path, kind: 'video', raw_url: `/knowledge/files/raw?user_id=media-user&path=${path}`,
      mime_type: 'video/mp4', mtime: '2026-08-20 00:00', size: 5, extension: '.mp4', readonly: true,
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path, content: markdown, mtime: '2026-08-20 00:00', size: markdown.length,
    })
    if (url.pathname === '/knowledge/files/raw') return route.fulfill({ status: 200, contentType: 'video/mp4', body: '' })
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'media-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()

  await page.getByRole('button', { name: 'clip.mp4 收藏' }).evaluate((element) => (element as HTMLElement).click())
  await expect(page.locator('video.video-preview')).toBeVisible()
  await expect(page.locator('video.video-preview')).toHaveAttribute('controls', '')
  await page.screenshot({ path: testInfo.outputPath('video-player.png'), fullPage: true })

  await page.getByRole('button', { name: 'media.md 收藏' }).evaluate((element) => (element as HTMLElement).click())
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  const htmlImage = page.locator('.markdown-preview .vditor-reset img[alt="HTML 图片"]')
  const htmlVideo = page.locator('.markdown-preview .vditor-reset iframe')
  await expect(htmlImage).toBeVisible()
  await expect(htmlVideo).toBeVisible()
  expect(await htmlImage.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBe(640)
  expect(await htmlImage.evaluate((element) => getComputedStyle(element).display)).toBe('block')
  expect(await htmlVideo.evaluate((element) => getComputedStyle(element).aspectRatio)).toBe('16 / 9')
  await page.screenshot({ path: testInfo.outputPath('video-and-markdown-media.png'), fullPage: true })
})
