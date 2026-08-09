/*
 * Smart literature table helper tests.
 *
 * Usage:
 * Run with Vitest to verify spreadsheet data transforms without mounting the
 * full Vue workspace.
 */

import { describe, expect, it } from 'vitest'

import {
  BUILTIN_COLUMNS,
  addColumn,
  createCustomColumn,
  createDefaultLiteratureForm,
  createEmptyRow,
  exportCsv,
  exportMarkdown,
  filterRows,
  joinTags,
  moveColumn,
  moveRow,
  normalizeForm,
  removeColumn,
  splitTags,
  uniqueTagValues,
  updateCell,
  type SmartColumn,
} from '@/components/smart_forms/smartLiteratureTable'

describe('smartLiteratureTable', () => {
  function rowWithValues(form: ReturnType<typeof createDefaultLiteratureForm>, values: Record<string, string>) {
    const row = createEmptyRow(form.columns)
    Object.entries(values).forEach(([columnId, value]) => {
      row.cells[columnId] = { ...row.cells[columnId], value }
    })
    return row
  }

  it('creates a literature form with stable default research columns', () => {
    const form = createDefaultLiteratureForm()

    expect(form.columns.map((column) => column.id)).toEqual([
      'row_index',
      'literature_file',
      'literature_content',
      'title',
    ])
    expect(form.columns.find((column) => column.id === 'literature_file')?.title).toBe('文献上传')
    expect(form.columns.find((column) => column.id === 'literature_content')?.editable).toBe(false)
    expect(form.rows).toHaveLength(1)
    expect(form.rows[0]?.cells.title?.value).toBe('')
    expect(form.rows[0]?.cells.literature_content?.value).toBe('')
  })

  it('updates smart cells as ready and keeps non-smart status untouched', () => {
    const form = addColumn(createDefaultLiteratureForm(), BUILTIN_COLUMNS.find((column) => column.id === 'rating')!)
    const titleColumn = form.columns.find((column) => column.id === 'title') as SmartColumn
    const ratingColumn = form.columns.find((column) => column.id === 'rating') as SmartColumn

    const updatedTitleRow = updateCell(form.rows[0]!, titleColumn, 'New title')
    const updatedRatingRow = updateCell(form.rows[0]!, ratingColumn, '5')

    expect(updatedTitleRow.cells.title?.value).toBe('New title')
    expect(updatedTitleRow.cells.title?.status).toBe('ready')
    expect(updatedRatingRow.cells.rating?.value).toBe('5')
    expect(updatedRatingRow.cells.rating?.status).toBeUndefined()
  })

  it('adds, removes, and moves columns while keeping row cells aligned', () => {
    const form = createDefaultLiteratureForm()
    const customColumn = createCustomColumn('是否精读', 'boolean')
    const added = addColumn(form, customColumn, 2)

    expect(added.columns[2]?.id).toBe(customColumn.id)
    expect(added.rows.every((row) => row.cells[customColumn.id]?.value === '')).toBe(true)

    const moved = moveColumn(added, customColumn.id, 1)
    expect(moved.columns[3]?.id).toBe(customColumn.id)

    const removed = removeColumn(moved, customColumn.id)
    expect(removed.columns.some((column) => column.id === customColumn.id)).toBe(false)
    expect(removed.rows.some((row) => row.cells[customColumn.id])).toBe(false)
  })

  it('does not remove non-removable index columns', () => {
    const form = createDefaultLiteratureForm()
    const removed = removeColumn(form, 'row_index')

    expect(removed.columns.map((column) => column.id)).toEqual(form.columns.map((column) => column.id))
  })

  it('moves rows within bounds only', () => {
    const form = createDefaultLiteratureForm()
    form.rows = [createEmptyRow(form.columns), createEmptyRow(form.columns)]
    const secondRowId = form.rows[1]!.id
    const moved = moveRow(form, secondRowId, -1)
    const unchanged = moveRow(moved, secondRowId, -1)

    expect(moved.rows[0]?.id).toBe(secondRowId)
    expect(unchanged.rows[0]?.id).toBe(secondRowId)
  })

  it('filters by full-table query, tag value, and minimum rating', () => {
    const formWithPaperType = addColumn(createDefaultLiteratureForm(), BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!)
    const form = addColumn(formWithPaperType, BUILTIN_COLUMNS.find((column) => column.id === 'rating')!)
    form.rows = [
      rowWithValues(form, {
        title: 'Autophagy mediates temporary reprogramming',
        rating: '3',
        paper_type: '研究论文',
      }),
      rowWithValues(form, {
        title: 'Reactive Oxygen Species review',
        rating: '5',
        paper_type: '综述论文',
      }),
    ]

    expect(filterRows(form, 'Autophagy', '', 0)).toHaveLength(1)
    expect(filterRows(form, '', '综述论文', 0)).toHaveLength(1)
    expect(filterRows(form, '', '', 5)).toHaveLength(1)
    expect(filterRows(form, 'Autophagy', '综述论文', 0)).toHaveLength(0)
  })

  it('exports CSV and Markdown without the literature file column', () => {
    const form = createDefaultLiteratureForm()
    form.rows[0]!.cells.title = { value: '真实上传后生成的标题', status: 'ready' }
    form.rows[0]!.cells.literature_content = { value: '真实抽取的文献内容' }
    const csv = exportCsv(form)
    const markdown = exportMarkdown(form)

    expect(csv.split('\n')[0]).toContain('标题')
    expect(csv.split('\n')[0]).not.toContain('文献上传')
    expect(csv).toContain('真实抽取的文献内容')
    expect(markdown).toContain('| 序号 | 文献内容 | 标题 |')
    expect(markdown).not.toContain('文献上传')
  })

  it('normalizes partial persisted forms against the current columns', () => {
    const form = createDefaultLiteratureForm()
    const normalized = normalizeForm({
      title: '恢复表',
      columns: form.columns,
      rows: [{ id: '', cells: { title: { value: 'Only title' } } }],
    })

    expect(normalized.title).toBe('恢复表')
    expect(normalized.rows[0]?.id).toMatch(/^row_/)
    expect(normalized.rows[0]?.cells.title?.value).toBe('Only title')
    expect(normalized.rows[0]?.cells.literature_content?.value).toBe('')
  })

  it('preserves persisted column order while normalizing required columns', () => {
    const form = createDefaultLiteratureForm()
    const reordered = normalizeForm({
      ...form,
      columns: [form.columns[0]!, form.columns[1]!, form.columns[3]!, form.columns[2]!],
    })

    expect(reordered.columns.map((column) => column.id).slice(0, 4)).toEqual([
      'row_index',
      'literature_file',
      'title',
      'literature_content',
    ])
  })

  it('renames the persisted literature upload column to literature upload', () => {
    const normalized = normalizeForm({
      columns: [{ ...createDefaultLiteratureForm().columns.find((column) => column.id === 'literature_file')!, title: '文献PDF上传' }],
      rows: [],
    })

    expect(normalized.columns[0]?.title).toBe('文献上传')
  })

  it('collects tag values from all tag-like columns', () => {
    const withReadingProgress = addColumn(createDefaultLiteratureForm(), BUILTIN_COLUMNS.find((column) => column.id === 'reading_progress')!)
    const form = addColumn(withReadingProgress, BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!)
    form.rows[0]!.cells.reading_progress = { value: '已读' }
    form.rows[0]!.cells.paper_type = { value: '方法论文', status: 'ready' }

    const tags = uniqueTagValues(form)

    expect(tags).toContain('已读')
    expect(tags).toContain('方法论文')
  })

  it('splits and joins multi-tag cell values', () => {
    expect(splitTags('研究论文; 重点;  综述论文 ')).toEqual(['研究论文', '重点', '综述论文'])
    expect(splitTags('')).toEqual([])
    expect(splitTags('未读')).toEqual(['未读'])
    expect(joinTags([' 研究论文 ', '重点', '', '研究论文'])).toBe('研究论文; 重点')
  })

  it('filters rows by any single tag inside a multi-tag cell', () => {
    const withReadingProgress = addColumn(createDefaultLiteratureForm(), BUILTIN_COLUMNS.find((column) => column.id === 'reading_progress')!)
    const form = addColumn(withReadingProgress, BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!)
    form.rows[0]!.cells.paper_type = { value: '研究论文; 重点', status: 'ready' }
    form.rows[0]!.cells.reading_progress = { value: '未读' }

    expect(filterRows(form, '', '重点', 0)).toHaveLength(1)
    expect(filterRows(form, '', '研究论文', 0)).toHaveLength(1)
    expect(filterRows(form, '', '未读', 0)).toHaveLength(1)
    expect(filterRows(form, '', '已读', 0)).toHaveLength(0)
  })

  it('collects every tag from multi-tag cells', () => {
    const withReadingProgress = addColumn(createDefaultLiteratureForm(), BUILTIN_COLUMNS.find((column) => column.id === 'reading_progress')!)
    const form = addColumn(withReadingProgress, BUILTIN_COLUMNS.find((column) => column.id === 'paper_type')!)
    form.rows[0]!.cells.reading_progress = { value: '未读; 重点' }
    form.rows[0]!.cells.paper_type = { value: '研究论文', status: 'ready' }

    const tags = uniqueTagValues(form)

    expect(tags).toEqual(expect.arrayContaining(['未读', '重点', '研究论文']))
  })
})
