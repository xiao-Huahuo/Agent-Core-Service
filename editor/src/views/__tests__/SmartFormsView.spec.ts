/*
 * Smart forms view smoke tests.
 *
 * Usage:
 * Mounts the literature table page with mocked knowledge-file APIs to verify
 * the first screen and core controls render without a backend process.
 */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { streamPrompt } from '@/api/agent'
import { createDefaultLiteratureForm } from '@/components/smart_forms/smartLiteratureTable'
import { listKnowledgeFiles, previewKnowledgeFile, readKnowledgeFile, uploadKnowledgeFile, writeKnowledgeFile } from '@/api/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import SmartFormsView from '@/views/SmartFormsView.vue'

vi.mock('@/api/agent', () => ({
  streamPrompt: vi.fn(async function* () {
    yield { content: '{"title":"LLM extracted title","keywords":"ROS; signaling","paper_type":"研究论文","journal":"Plant Cell"}' }
  }),
  updateCurrentDocumentContext: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/settings', () => ({
  rebuildKnowledgeRootStream: vi.fn(),
}))

vi.mock('@/api/knowledge', () => ({
  buildKnowledgeEventsUrl: vi.fn(() => '/events'),
  copyKnowledgePath: vi.fn(),
  createKnowledgeFile: vi.fn(),
  createKnowledgeFolder: vi.fn().mockResolvedValue({}),
  deleteKnowledgePath: vi.fn(),
  deleteKnowledgeTrashEntry: vi.fn(),
  getKnowledgeGraphStatus: vi.fn(),
  ingestKnowledgeFileStream: vi.fn(),
  ingestKnowledgePathStream: vi.fn(),
  listKnowledgeFiles: vi.fn().mockResolvedValue({
    tree: [{
      name: 'forms',
      path: 'forms',
      isDir: true,
      children: [{ name: '我的文献表', path: 'forms/我的文献表', isDir: true }],
    }],
  }),
  listKnowledgeTrash: vi.fn(),
  previewKnowledgeFile: vi.fn(),
  readKnowledgeFile: vi.fn().mockResolvedValue({
    path: 'forms/我的文献表/form.json',
    content: JSON.stringify(createDefaultLiteratureForm('我的文献表')),
    mtime: '2026-08-09T10:00:00',
    size: 100,
  }),
  rebuildKnowledgeGraph: vi.fn(),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  searchKnowledge: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn().mockResolvedValue({}),
}))

describe('SmartFormsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    useSettingsStore().updateProfile({ userId: 'local-test', knowledgeDir: 'D:/Knowledge' })
  })

  it('renders a user-created smart literature table from forms', async () => {
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    expect(readKnowledgeFile).toHaveBeenCalledWith('local-test', 'forms/我的文献表/form.json')
    expect(wrapper.get('h1').text()).toBe('我的文献表')
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('The missing link')
  })

  it('shows a creation empty state instead of creating a fake default table', async () => {
    vi.mocked(listKnowledgeFiles).mockResolvedValueOnce({ tree: [] })

    const wrapper = mount(SmartFormsView)
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('创建你的第一张表')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(readKnowledgeFile).not.toHaveBeenCalled()
  })

  it('creates a user-named form under the knowledge forms folder', async () => {
    vi.mocked(listKnowledgeFiles).mockResolvedValueOnce({ tree: [] })
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.find('button[title="新建表格"]').trigger('click')
    await wrapper.find('input[placeholder="例如：项目文献库"]').setValue('项目阅读表')
    await wrapper.find('form[role="dialog"]').trigger('submit')
    await flushPromises()

    expect(writeKnowledgeFile).toHaveBeenCalledWith(
      'local-test',
      'forms/项目阅读表/form.json',
      expect.stringContaining('"title": "项目阅读表"'),
    )
  })

  it('adds rows and generates selected smart cells from literature content', async () => {
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('添加记录'))?.trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)

    const literatureContentTextarea = wrapper.findAll('textarea')[0]!
    await literatureContentTextarea.setValue('A paper about ROS receptor HPCA1 in systemic signaling.')
    await wrapper.findAll('td.cell')[3]?.trigger('click')
    await wrapper.find('button[title="重新生成该格"]').trigger('click')
    await flushPromises()

    const textareaValues = wrapper.findAll('textarea').map((textarea) => {
      return (textarea.element as HTMLTextAreaElement).value
    })
    expect(textareaValues).toContain('LLM extracted title')
    expect(wrapper.text()).not.toContain('AI 生成')
  })

  it('falls back to document extraction when smart fill returns invalid JSON', async () => {
    vi.mocked(streamPrompt).mockImplementationOnce(async function* () {
      yield { content: 'not json' }
    })
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    const literatureContentTextarea = wrapper.findAll('textarea')[0]!
    await literatureContentTextarea.setValue([
      '## 表格PDF',
      '摘要: 项目案例库用于演示智能表格抽取。',
      'Keywords: CRUD; archive; workspace',
      'DOI: 10.1234/metawave.demo',
      '2026',
    ].join('\n'))
    await wrapper.findAll('button').find((button) => button.text().includes('全表智能填充'))?.trigger('click')
    await flushPromises()

    const textareaValues = wrapper.findAll('textarea').map((textarea) => {
      return (textarea.element as HTMLTextAreaElement).value
    })
    expect(textareaValues).toContain('表格PDF')
    expect(textareaValues).toContainEqual(expect.stringContaining('CRUD'))
    expect(wrapper.find('.status-dot.failed').exists()).toBe(false)
  })

  it('uploads literature assets without hidden auto ingest and submits stream ingestion', async () => {
    vi.mocked(uploadKnowledgeFile).mockResolvedValueOnce({
      uploaded_path: 'D:/Knowledge/forms/我的文献表/assets/paper.md',
      knowledge_dir: 'D:/Knowledge',
    })
    vi.mocked(previewKnowledgeFile).mockResolvedValueOnce({
      path: 'forms/我的文献表/assets/paper.md',
      kind: 'markdown',
      content: '这是灌库后从文献中抽取出的真实正文。',
      mtime: '2026-08-09T10:00:00',
      size: 128,
      extension: '.md',
      readonly: false,
    })
    const workspaceStore = useWorkspaceStore()
    const ingestFile = vi.spyOn(workspaceStore, 'ingestFile').mockResolvedValue(undefined)
    const wrapper = mount(SmartFormsView)
    await flushPromises()
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', {
      value: [new File(['paper text'], 'paper.md', { type: 'text/markdown' })],
      configurable: true,
    })

    await wrapper.get('input[type="file"]').trigger('change')
    await flushPromises()

    expect(uploadKnowledgeFile).toHaveBeenCalledWith(
      'local-test',
      expect.any(File),
      'forms/我的文献表/assets',
      false,
      'rename',
    )
    expect(ingestFile).toHaveBeenCalledWith({
      name: 'paper.md',
      path: 'forms/我的文献表/assets/paper.md',
      isDir: false,
      indexStatus: 'dirty',
    })
    expect(previewKnowledgeFile).toHaveBeenCalledWith('local-test', 'forms/我的文献表/assets/paper.md')
    const textareaValues = wrapper.findAll('textarea').map((textarea) => {
      return (textarea.element as HTMLTextAreaElement).value
    })
    expect(textareaValues).toContain('这是灌库后从文献中抽取出的真实正文。')
    expect(writeKnowledgeFile).toHaveBeenCalledWith(
      'local-test',
      'forms/我的文献表/form.json',
      expect.stringContaining('这是灌库后从文献中抽取出的真实正文。'),
    )
    expect(wrapper.find('.status-dot').exists()).toBe(false)
  })
})
