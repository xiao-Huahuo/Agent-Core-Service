/** Per-file ingestion-to-graph queue orchestration regression tests. */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelKnowledgeGraphTask,
  cancelKnowledgeIngestionJob,
  createKnowledgeIngestionJobs,
  getKnowledgeGraphStatus,
  listKnowledgeIngestionJobs,
  rebuildKnowledgeGraph,
} from '@/api/knowledge'
import type { KnowledgeIngestionJob } from '@/api/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

vi.mock('@/api/agent', () => ({ updateCurrentDocumentContext: vi.fn().mockResolvedValue(undefined) }))
vi.mock('@/api/knowledge', () => ({
  buildKnowledgeEventsUrl: vi.fn(() => '/events'),
  cancelKnowledgeGraphTask: vi.fn().mockResolvedValue({ status: 'cancelling', message: 'cancelling' }),
  cancelKnowledgeIngestionJob: vi.fn().mockResolvedValue(undefined),
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

  it('updates header ingestion detail and aggregate progress immediately after cancellation', async () => {
    vi.mocked(listKnowledgeIngestionJobs)
      .mockResolvedValueOnce({ jobs: [job('first.md', 'running')] })
      .mockResolvedValue({ jobs: [job('first.md', 'cancelled')] })
    const store = useWorkspaceStore()

    await store.loadIngestionJobs()
    expect(store.ingestionProgressVisible).toBe(true)
    expect(store.ingestionProgressDetail).toContain('first.md · running')

    await store.cancelIngestionJob(store.ingestionQueue[0]!)

    expect(cancelKnowledgeIngestionJob).toHaveBeenCalledWith('user-1', 'job-first.md')
    expect(store.ingestionProgress).toBe(100)
    expect(store.ingestionProgressDetail).toBe('first.md · 已中止')
    expect(store.ingestionProgressStats).toEqual({ succeeded: 0, total: 1, failed: 1 })
  })

  it('optimistically marks a graph row cancelling and applies the polled terminal state', async () => {
    vi.mocked(getKnowledgeGraphStatus).mockResolvedValue({
      status: 'cancelled',
      total: 1,
      current: 1,
      message: '图谱抽取已中止',
      docs: [{ path: 'first.md', name: 'first.md', status: 'cancelled', progress: 100 }],
    })
    const store = useWorkspaceStore()
    store.graphProgressVisible = true
    store.graphQueue = [{
      id: 'graph-first',
      name: 'first.md',
      path: 'first.md',
      isDir: false,
      status: 'running',
      progress: 40,
      stageLabel: '正在抽取实体',
      queuedAt: '2026-08-31T01:00:01Z',
    }]

    await store.cancelGraphTask(store.graphQueue[0]!)

    expect(cancelKnowledgeGraphTask).toHaveBeenCalledWith('user-1', 'first.md')
    expect(store.graphQueue).toEqual([])
    expect(store.graphProgress).toBe(100)
    expect(store.graphProgressDetail).toBe('图谱抽取已中止')
    expect(store.graphHistory[0]?.status).toBe('cancelled')
  })
})
