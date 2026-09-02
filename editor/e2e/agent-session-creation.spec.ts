/**
 * Agent new-conversation creation timing browser smoke test.
 *
 * Usage:
 * Exercises the real Agent page and records session POSTs to prove that UI
 * clicks stay local while the first visible user bubble creates one session.
 */
import { expect, test } from '@playwright/test'

test('creates a new conversation only when the first user bubble is sent', async ({ page }) => {
  let createdSessions = 0
  const sessions: Array<Record<string, string>> = []
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/sessions' && request.method() === 'POST') {
      createdSessions += 1
      const session = {
        session_id: `first-bubble-session-${createdSessions}`,
        user_id: 'e2e-user',
        session_name: `第 ${createdSessions} 个对话`,
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      }
      sessions.unshift(session)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(session),
      })
      return
    }
    if (url.pathname === '/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessions),
      })
      return
    }
    if (url.pathname === '/agent/stream') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user_id: 'e2e-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [] }),
      })
      return
    }
    if (url.pathname === '/settings/models/management') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"models":[]}' })
      return
    }
    if (url.pathname === '/favorites') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"favorites":[]}' })
      return
    }
    if (url.pathname === '/privacy') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"privacy":[]}' })
      return
    }
    if (url.pathname === '/agent/children') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ session_id: url.searchParams.get('session_id') || '', children: [] }),
      })
      return
    }
    if (url.pathname === '/todo/list' || url.pathname === '/automation/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (url.pathname === '/knowledge/files') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"tree":[]}' })
      return
    }
    if (url.pathname === '/knowledge/files/events') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
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
      userId: 'e2e-user',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.getByPlaceholder('输入消息...').fill('第一条消息')
  await page.getByTitle('发送').click()
  await expect.poll(() => createdSessions).toBe(1)
  await expect(page.getByText('第一条消息', { exact: true })).toBeVisible()

  const newConversation = page.locator('.panel-new-session')
  await newConversation.click()
  await newConversation.click()
  expect(createdSessions).toBe(1)
  await expect(page.getByText('第一条消息', { exact: true })).toHaveCount(0)

  await page.getByPlaceholder('输入消息...').fill('第二个对话的第一条消息')
  await page.getByTitle('发送').click()

  await expect.poll(() => createdSessions).toBe(2)
  await expect(page.getByText('第二个对话的第一条消息', { exact: true })).toBeVisible()
})
