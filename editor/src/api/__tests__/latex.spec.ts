/**
 * LaTeX API 客户端请求构造测试。
 *
 * 使用说明:
 * 验证编译、运行时状态、安装、取消和卸载全部调用正式后端接口。
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  cancelLatexInstall,
  compileLatexFile,
  fetchLatexStatus,
  fetchLatexManagement,
  installLatexRuntime,
  uninstallLatexRuntime,
} from '@/api/latex'

describe('LaTeX API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('constructs status and compile requests with encoded user data', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      status: 'ready',
      source: 'system',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchLatexStatus('user/1')
    await compileLatexFile('user/1', 'papers/main.tex')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/latex/status?user_id=user%2F1')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/knowledge/latex/compile')
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      user_id: 'user/1',
      path: 'papers/main.tex',
    })
  })

  it('connects every runtime lifecycle action to its backend endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await installLatexRuntime('u1')
    await cancelLatexInstall('u1')
    await uninstallLatexRuntime('u1')

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/settings/latex/install',
      '/settings/latex/install/cancel',
      '/settings/latex/uninstall',
    ])
  })

  it('loads compiler-management details through the dedicated settings endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      status: 'ready', source: 'system', distribution_path: 'D:/MiKTeX', engines: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchLatexManagement('user/1')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/latex/management?user_id=user%2F1')
  })
})
