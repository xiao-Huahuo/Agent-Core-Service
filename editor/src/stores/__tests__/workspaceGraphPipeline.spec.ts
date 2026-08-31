/** Per-file ingestion-to-graph queue orchestration regression tests. */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createKnowledgeIngestionJobs,
  listKnowledgeIngestionJobs,
  rebuildKnowledgeGraph,
} from '@/api/knowledge'
import type { KnowledgeIngestionJob } from '@/api/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

vi.mock('@/api/agent', () => ({ updateCurrentDocumentContext: vi.fn().mockResolvedValue(undefined) }))
vi.mock('@/api/knowledge', () => ({
  buildKnowledgeEventsUrl: vi.fn(() => '/events'),
  cancelKnowledgeIngestionJob: vi.fn(),
  copyKnowledgePath: vi.fn(),
  createKnowledgeFile: vi.fn(),
  createKnowledgeFolder: vi.fn(),
  createKnowledgeIngestionJobs: vi.fn(),
  deleteKnowledgePath: vi.fn(),
  deleteKnowledgeTrashEntry: vi.fn(),
  getKnowledgeGraphStatus: vi.fn().mockResolvedValue({
    status: 'completed', total: 1, current: 1, message: 'done', docs: [],
  }),
  listKnowledgeFiles: vi.fn(),
  listKnowledgeIngestionJobs: vi.fn(),
  listKnowledgeTrash: vi.fn(),
  previewKnowledgeFile: vi.fn(),
  readKnowledgeFile: vi.fn(),
  rebuildKnowledgeGraph: vi.fn().mockResolvedValue({ status: 'queued', message: 'queued' }),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn(),
}))

function job(path: string, status: KnowledgeIngestionJob['status']): KnowledgeIngestionJob {
  return {
    job_id: `job-${path}`,
    user_id: 'user-1',
    library_id: 'library-1',
    path,
    name: path,
    pipeline: 'markdown',
    status,
    stage: status,
    stage_label: status,
    progress: status === 'finished' ? 100 : 20,
    stage_current: 0,
    stage_total: 1,
    message: '',
    error: '',
    created_at: `2026-08-31T01:00:0${path === 'first.md' ? '1' : '2'}Z`,
    updated_at: '2026-08-31T01:00:03Z',
  }
}

describe('workspace per-file graph pipeline', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    useSettingsStore().profile.userId = 'user-1'
    const knowledgeApi = await import('@/api/knowledge')
    vi.mocked(knowledgeApi.listKnowledgeFiles).mockResolvedValue({
      tree: [
        { name: 'first.md', path: 'first.md', isDir: false, indexStatus: 'dirty' },
        { name: 'second.md', path: 'second.md', isDir: false, indexStatus: 'dirty' },
      ],
    })
    vi.mocked(createKnowledgeIngestionJobs).mockResolvedValue({
      jobs: [job('first.md', 'queued'), job('second.md', 'queued')],
    })
  })

  it('enqueues the first finished file before the second ingestion finishes', async () => {
    vi.mocked(listKnowledgeIngestionJobs)
      .mockResolvedValueOnce({ jobs: [job('first.md', 'finished'), job('second.md', 'running')] })
      .mockResolvedValueOnce({ jobs: [job('first.md', 'finished'), job('second.md', 'running')] })
      .mockResolvedValue({ jobs: [job('first.md', 'finished'), job('second.md', 'finished')] })
    const store = useWorkspaceStore()

    await store.startGraphRebuild()

    await vi.waitFor(() => expect(rebuildKnowledgeGraph).toHaveBeenCalledWith('user-1', 'first.md', false))
    expect(vi.mocked(rebuildKnowledgeGraph).mock.calls.some((call) => call[1] === 'second.md')).toBe(false)
    await vi.waitFor(
      () => expect(rebuildKnowledgeGraph).toHaveBeenCalledWith('user-1', 'second.md', false),
      { timeout: 1_000 },
    )
  })

  it('accepts repeated one-click extraction while the first submission is active', async () => {
    vi.mocked(listKnowledgeIngestionJobs).mockResolvedValue({
      jobs: [job('first.md', 'finished'), job('second.md', 'finished')],
    })
    const store = useWorkspaceStore()

    await Promise.all([store.startGraphRebuild(), store.startGraphRebuild()])

    await vi.waitFor(() => expect(createKnowledgeIngestionJobs).toHaveBeenCalledTimes(2))
  })
})
