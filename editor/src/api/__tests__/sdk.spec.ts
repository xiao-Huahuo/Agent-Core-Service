/* SDK管理 API 路由、查询与请求体构造测试。 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelDshSdkInstall,
  fetchDshSdkManagement,
  installDshSdk,
  initializeDshCodingAgent,
  repairDshSdk,
  uninstallDshSdk,
} from '@/api/sdk'

const fetchMock = vi.fn()

describe('DSH SDK management API', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation(async () => new Response(JSON.stringify({ status: 'missing' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
  })

  it('uses the registered status query route', async () => {
    await fetchDshSdkManagement('user/1')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/sdks/dsh/management?user_id=user%2F1')
  })

  it('posts every lifecycle operation with the user id', async () => {
    await installDshSdk('u1')
    await initializeDshCodingAgent('u1')
    await cancelDshSdkInstall('u1')
    await repairDshSdk('u1')
    await uninstallDshSdk('u1')
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      '/settings/sdks/dsh/install',
      '/settings/sdks/dsh/initialize',
      '/settings/sdks/dsh/install/cancel',
      '/settings/sdks/dsh/repair',
      '/settings/sdks/dsh/uninstall',
    ])
    for (const call of fetchMock.mock.calls) {
      expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({ user_id: 'u1' })
    }
  })
})
