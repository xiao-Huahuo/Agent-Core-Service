/*
 * Git API client tests.
 *
 * Usage:
 * Verifies that the typed client uses the central route registry and preserves
 * structured file selections and push safety flags.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { addGitRemote, commitGitPaths, fetchGitStatus, pushGitBranch } from '@/api/git'
import { ApiError } from '@/api/client'

describe('Git API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads repository status for the active user', async () => {
    const payload = {
      initialized: true,
      repository_root: 'D:/knowledge',
      current_branch: 'main',
      upstream: 'origin/main',
      ahead: 0,
      behind: 0,
      detached: false,
      branches: [],
      remote_branches: [],
      remotes: ['origin'],
      changes: [],
      untracked: [],
      has_changes: false,
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchGitStatus('user-1')).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/git/status?user_id=user-1')
  })

  it('posts only selected files and the commit summary', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true, status: {} }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await commitGitPaths('user-1', ['notes/a.md'], 'update note')

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(request.body))).toEqual({
      user_id: 'user-1',
      paths: ['notes/a.md'],
      message: 'update note',
    })
  })

  it('uses force-with-lease instead of an unsafe force flag', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true, status: {}, output: '' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await pushGitBranch('user-1', {
      localBranch: 'main',
      remote: 'origin',
      remoteBranch: 'main',
      forceWithLease: true,
      allBranches: true,
    })

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(request.body))).toMatchObject({
      force_with_lease: true,
      set_upstream: true,
      all_branches: true,
    })
  })

  it('reports a clear API error when the server returns HTML instead of JSON', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('<!doctype html><title>MetaWeave</title>', {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const request = fetchGitStatus('user-1')

    await expect(request).rejects.toBeInstanceOf(ApiError)
    await expect(request).rejects.toThrow('/git/status')
    await expect(request).rejects.toThrow('text/html')
  })

  it('posts a new remote name and repository URL', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ initialized: true, remotes: ['origin'] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await addGitRemote('user-1', 'origin', 'git@example.com:team/notes.git')

    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/git/remotes')
    expect(JSON.parse(String(request.body))).toEqual({
      user_id: 'user-1',
      name: 'origin',
      url: 'git@example.com:team/notes.git',
    })
  })
})
