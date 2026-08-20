/** Single-file ingestion queue progress and cancellation UI tests. */

import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import IngestionProgressView from '@/views/IngestionProgressView.vue'

const cancelIngestionJob = vi.fn().mockResolvedValue(undefined)
const loadIngestionJobs = vi.fn().mockResolvedValue([])
const workspaceStore = {
  ingestionViewTab: 'queue',
  mainView: 'ingestion',
  refreshing: false,
  ingestionQueue: [{
    id: 'ingest_1',
    jobId: 'ingest_1',
    name: 'paper.pdf',
    path: 'papers/paper.pdf',
    isDir: false,
    size: 2048,
    mtime: '2026-08-20 18:00',
    status: 'running',
    progress: 64,
    pipeline: 'pdf',
    stage: 'ocr_pages',
    stageLabel: '正在 OCR 扫描页',
    stageCurrent: 8,
    stageTotal: 20,
    queuedAt: '2026-08-20T10:00:00Z',
    message: '已识别第 8 / 20 页',
  }],
  graphQueue: [],
  ingestionHistory: [],
  graphHistory: [],
  loadIngestionJobs,
  cancelIngestionJob,
  clearIngestionHistory: vi.fn(),
  clearGraphHistory: vi.fn(),
  loadKnowledgeTree: vi.fn().mockResolvedValue(undefined),
  markIndexing: vi.fn(),
  startGraphRebuild: vi.fn(),
}

vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: () => workspaceStore,
}))

describe('IngestionProgressView', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('shows real file pipeline detail and cancels that exact job', async () => {
    const wrapper = mount(IngestionProgressView, {
      global: { stubs: { IcIcon: true } },
    })

    expect(wrapper.text()).toContain('灌库进度')
    expect(wrapper.text()).toContain('paper.pdf')
    expect(wrapper.text()).toContain('64%')
    expect(wrapper.text()).toContain('正在 OCR 扫描页')
    expect(wrapper.text()).toContain('8 / 20')

    await wrapper.get('button[aria-label="中止 paper.pdf 灌库"]').trigger('click')

    expect(cancelIngestionJob).toHaveBeenCalledWith(workspaceStore.ingestionQueue[0])
  })
})
