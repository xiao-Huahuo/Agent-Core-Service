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
import { getSmartFormDb, listSmartFormsDb, saveSmartFormDb } from '@/api/smartForms'
import { BUILTIN_COLUMNS, addColumn, createDefaultLiteratureForm, type SmartLiteratureForm } from '@/components/smart_forms/smartLiteratureTable'
import { previewKnowledgeFile, readKnowledgeFile, uploadKnowledgeFile } from '@/api/knowledge'
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

vi.mock('@/api/smartForms', () => ({
  getSmartFormDb: vi.fn(),
  listSmartFormsDb: vi.fn(),
  saveSmartFormDb: vi.fn(),
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
  listKnowledgeFiles: vi.fn().mockResolvedValue({ tree: [] }),
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
  writeKnowledgeFile: vi.fn(),
}))

describe('SmartFormsView', () => {
  function dbResponse(form: SmartLiteratureForm, formId = 'sf_demo') {
    return {
      form_id: formId,
      user_id: 'local-test',
      asset_dir: `forms/${form.title}`,
      form,
      updated_at: '2026-08-09T10:00:00',
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    useSettingsStore().updateProfile({ userId: 'local-test', knowledgeDir: 'D:/Knowledge' })
    const defaultForm = createDefaultLiteratureForm('我的文献表')
    vi.mocked(listSmartFormsDb).mockResolvedValue([{
      form_id: 'sf_demo',
      title: '我的文献表',
      asset_dir: 'forms/我的文献表',
      updated_at: '2026-08-09T10:00:00',
    }])
    vi.mocked(getSmartFormDb).mockResolvedValue(dbResponse(defaultForm))
    vi.mocked(saveSmartFormDb).mockImplementation(async (payload) => {
      return dbResponse(payload.form, payload.form_id || 'sf_saved')
    })
  })

  it('renders a user-created smart literature table from forms', async () => {
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    expect(getSmartFormDb).toHaveBeenCalledWith('local-test', 'sf_demo')
    expect(wrapper.get('h1').text()).toBe('我的文献表')
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('The missing link')
  })

  it('shows a creation empty state instead of creating a fake default table', async () => {
    vi.mocked(listSmartFormsDb).mockResolvedValueOnce([])

    const wrapper = mount(SmartFormsView)
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('创建你的第一张表')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(getSmartFormDb).not.toHaveBeenCalled()
  })

  it('adds a new row from the toolbar action', async () => {
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('新建行'))?.trigger('click')

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('新建列')
  })

  it('creates a user-named form under the knowledge forms folder', async () => {
    vi.mocked(listSmartFormsDb).mockResolvedValueOnce([])
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.find('button[title="新建表格"]').trigger('click')
    await wrapper.find('input[placeholder="例如：项目文献库"]').setValue('项目阅读表')
    await wrapper.find('form[role="dialog"]').trigger('submit')
    await flushPromises()

    expect(saveSmartFormDb).toHaveBeenCalledWith(expect.objectContaining({
      user_id: 'local-test',
      asset_dir: 'forms/项目阅读表',
      form: expect.objectContaining({ title: '项目阅读表' }),
    }))
  })

  it('adds rows and generates selected smart cells from literature content', async () => {
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.find('tbody tr').trigger('contextmenu')
    await wrapper.findAll('button').find((button) => button.text().includes('添加行'))?.trigger('mouseenter')
    await wrapper.findAll('button').find((button) => button.text().includes('在下方添加'))?.trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)

    vi.mocked(uploadKnowledgeFile).mockResolvedValueOnce({
      uploaded_path: 'D:/Knowledge/forms/我的文献表/assets/ros.md',
      knowledge_dir: 'D:/Knowledge',
    })
    vi.mocked(previewKnowledgeFile).mockResolvedValueOnce({
      path: 'forms/我的文献表/assets/ros.md',
      kind: 'markdown',
      content: 'A paper about ROS receptor HPCA1 in systemic signaling.',
      mtime: '2026-08-09T10:00:00',
      size: 128,
      extension: '.md',
      readonly: false,
    })
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', {
      value: [new File(['paper text'], 'ros.md', { type: 'text/markdown' })],
      configurable: true,
    })
    await wrapper.get('input[type="file"]').trigger('change')
    await flushPromises()

    await wrapper.find('td[data-column-id="title"]').trigger('contextmenu')
    await wrapper.findAll('button').find((button) => button.text().includes('智能填充'))?.trigger('click')
    await flushPromises()

    const textareaValues = wrapper.findAll('textarea').map((textarea) => {
      return (textarea.element as HTMLTextAreaElement).value
    })
    expect(textareaValues).toContain('LLM extracted title')
    expect(wrapper.text()).not.toContain('AI 生成')
  })

  it('closes the tag picker when clicking outside it', async () => {
    const paperTypeColumn = BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!
    vi.mocked(getSmartFormDb).mockResolvedValueOnce(dbResponse(addColumn(createDefaultLiteratureForm('我的文献表'), paperTypeColumn)))
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    await wrapper.find('td[data-column-id="paper_type"] .tag-add-button').trigger('click')
    expect(wrapper.find('.tag-editor').exists()).toBe(true)

    await wrapper.find('.forms-header').trigger('click')
    expect(wrapper.find('.tag-editor').exists()).toBe(false)
  })

  it('adds multiple tags into one cell and toggles each off', async () => {
    const paperTypeColumn = BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!
    vi.mocked(getSmartFormDb).mockResolvedValueOnce(dbResponse(addColumn(createDefaultLiteratureForm('我的文献表'), paperTypeColumn)))
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    const cell = wrapper.find('td[data-column-id="paper_type"]')
    await cell.find('.tag-add-button').trigger('click')
    expect(wrapper.find('.tag-editor').exists()).toBe(true)

    await wrapper.findAll('.tag-option-pill').filter((pill) => pill.text().includes('研究论文'))[0]!.trigger('click')
    await flushPromises()
    await wrapper.findAll('.tag-option-pill').filter((pill) => pill.text().includes('综述论文'))[0]!.trigger('click')
    await flushPromises()

    const labelTexts = (): string[] => cell.findAll('.tag-pill-label').map((pill) => pill.text().trim())
    expect(labelTexts()).toEqual(expect.arrayContaining(['研究论文', '综述论文']))

    await wrapper.findAll('.tag-option-pill').filter((pill) => pill.text().includes('研究论文'))[0]!.trigger('click')
    await flushPromises()
    expect(labelTexts()).toEqual(['综述论文'])
  })

  it('adds a typed custom tag and renders it as a colored pill', async () => {
    const paperTypeColumn = BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!
    vi.mocked(getSmartFormDb).mockResolvedValueOnce(dbResponse(addColumn(createDefaultLiteratureForm('我的文献表'), paperTypeColumn)))
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    const cell = wrapper.find('td[data-column-id="paper_type"]')
    await cell.find('.tag-add-button').trigger('click')
    await cell.find('.tag-editor-input-row input').setValue('重点')
    await cell.find('.tag-editor-input-row button').trigger('click')
    await flushPromises()

    expect(cell.findAll('.tag-pill-label').map((pill) => pill.text().trim())).toEqual(['重点'])
    expect(cell.find('.tag-pill').attributes('style')).toContain('background')
  })

  it('falls back to document extraction when smart fill returns invalid JSON', async () => {
    vi.mocked(streamPrompt).mockImplementationOnce(async function* () {
      yield { content: 'not json' }
    })
    const wrapper = mount(SmartFormsView)
    await flushPromises()

    vi.mocked(uploadKnowledgeFile).mockResolvedValueOnce({
      uploaded_path: 'D:/Knowledge/forms/我的文献表/assets/table.md',
      knowledge_dir: 'D:/Knowledge',
    })
    vi.mocked(previewKnowledgeFile).mockResolvedValueOnce({
      path: 'forms/我的文献表/assets/table.md',
      kind: 'markdown',
      content: [
        '## 表格PDF',
        '摘要: 项目案例库用于演示智能表格抽取。',
        'Keywords: CRUD; archive; workspace',
        'DOI: 10.1234/metawave.demo',
        '2026',
      ].join('\n'),
      mtime: '2026-08-09T10:00:00',
      size: 128,
      extension: '.md',
      readonly: false,
    })
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', {
      value: [new File(['paper text'], 'table.md', { type: 'text/markdown' })],
      configurable: true,
    })
    await wrapper.get('input[type="file"]').trigger('change')
    await flushPromises()
    expect(wrapper.find('td[data-column-id="literature_content"] textarea').element).toMatchObject({
      value: [
      '## 表格PDF',
      '摘要: 项目案例库用于演示智能表格抽取。',
      'Keywords: CRUD; archive; workspace',
      'DOI: 10.1234/metawave.demo',
      '2026',
    ].join('\n'),
    })
    await wrapper.findAll('button').find((button) => button.text().includes('全表智能填充'))?.trigger('click')
    await flushPromises()

    const textareaValues = wrapper.findAll('textarea').map((textarea) => {
      return (textarea.element as HTMLTextAreaElement).value
    })
    expect(textareaValues).toContainEqual(expect.stringContaining('表格PDF'))
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
    expect(saveSmartFormDb).toHaveBeenCalledWith(expect.objectContaining({
      user_id: 'local-test',
      form_id: 'sf_demo',
      form: expect.objectContaining({
        rows: expect.arrayContaining([
          expect.objectContaining({
            cells: expect.objectContaining({
              literature_content: expect.objectContaining({ value: '这是灌库后从文献中抽取出的真实正文。' }),
            }),
          }),
        ]),
      }),
    }))
    expect(wrapper.find('.status-dot').exists()).toBe(false)
  })
})
