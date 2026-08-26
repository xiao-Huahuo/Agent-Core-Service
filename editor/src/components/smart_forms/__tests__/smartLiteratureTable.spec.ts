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
  DEFAULT_ROW_HEIGHT,
  INDEX_COLUMN_WIDTH,
  MIN_COLUMN_WIDTH,
  MIN_ROW_HEIGHT,
  PLAIN_ROW_HEIGHT,
  addColumn,
  createCustomColumn,
  createDefaultLiteratureForm,
  createDefaultPlainForm,
  createEmptyRow,
  exportCsv,
  exportMarkdown,
  extractMarkdownImages,
  filterRows,
  joinTags,
  moveColumn,
  moveRow,
  normalizeForm,
  removeColumn,
  resizeColumn,
  resizeRow,
  splitTags,
  insertMarkdownImage,
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
      'figures',
      'title',
    ])
    expect(form.columns.find((column) => column.id === 'literature_file')?.title).toBe('文献上传')
    expect(form.columns.find((column) => column.id === 'row_index')?.width).toBe(INDEX_COLUMN_WIDTH)
    expect(INDEX_COLUMN_WIDTH).toBe(32)
    expect(MIN_COLUMN_WIDTH).toBe(21)
    expect(form.columns.find((column) => column.id === 'literature_content')?.editable).toBe(false)
    expect(form.rows).toHaveLength(1)
    expect(form.rows[0]?.height).toBe(DEFAULT_ROW_HEIGHT)
    expect(form.rows[0]?.cells.title?.value).toBe('')
    expect(form.rows[0]?.cells.literature_content?.value).toBe('')
    expect(form.rows[0]?.cells.figures?.value).toBe('')
    expect(BUILTIN_COLUMNS.find((column) => column.id === 'figures')).toMatchObject({
      title: '图表',
      type: 'readonly_text',
      editable: false,
    })
    expect(form.columns.some((column) => column.id === 'formulas')).toBe(false)
  })

  it('registers formulas as an optional smart field with strict LaTeX guidance', () => {
    const formulaColumn = BUILTIN_COLUMNS.find((column) => column.id === 'formulas')

    expect(formulaColumn).toMatchObject({ title: '公式', type: 'smart_text', removable: true, editable: true })
    expect(formulaColumn?.description).toContain('主要 LaTeX 数学公式')
    expect(formulaColumn?.description).toContain('单个符号及过短表达式')
    expect(formulaColumn?.description).toContain('$$...$$')
  })

  it('gives every required and optional built-in column a default description', () => {
    const builtins = [...new Map(
      [...createDefaultLiteratureForm().columns, ...BUILTIN_COLUMNS].map((column) => [column.id, column]),
    ).values()]

    expect(builtins.every((column) => Boolean(column.description?.trim()))).toBe(true)
  })

  it('restores missing built-in descriptions without replacing user guidance', () => {
    const formulaColumn = BUILTIN_COLUMNS.find((column) => column.id === 'formulas')!
    const legacy = addColumn(createDefaultLiteratureForm(), { ...formulaColumn, description: undefined })
    legacy.columns = legacy.columns.map((column) => ({
      ...column,
      description: column.id === 'title' ? '用户自定义标题提示' : undefined,
    }))

    const normalized = normalizeForm(legacy)

    expect(normalized.columns.every((column) => Boolean(column.description?.trim()))).toBe(true)
    expect(normalized.columns.find((column) => column.id === 'title')?.description).toBe('用户自定义标题提示')
    expect(normalized.columns.find((column) => column.id === 'formulas')?.description).toContain('$$...$$')
  })

  it('collects every unique Markdown image from ingested PDF projections', () => {
    const semanticMarkdown = '# Paper\n\n![Figure 1](/.mw/assets/paper/image_0001.png)\n\n正文'
    const renderMarkdown = [
      '## Page 1',
      '![Figure 1](/.mw/assets/paper/image_0001.png)',
      '![Figure 2](/.mw/assets/paper/image_0002.png)',
    ].join('\n\n')

    expect(extractMarkdownImages(semanticMarkdown, renderMarkdown)).toBe([
      '![Figure 1](/.mw/assets/paper/image_0001.png)',
      '![Figure 2](/.mw/assets/paper/image_0002.png)',
    ].join('\n\n'))
  })

  it('creates a plain table with ten empty text columns and ten one-line rows', () => {
    const form = normalizeForm(createDefaultPlainForm('普通表格'))

    expect(form.columns).toHaveLength(10)
    expect(form.columns.every((column) => column.type === 'text')).toBe(true)
    expect(form.columns.some((column) => column.type === 'index' || column.id === 'row_index')).toBe(false)
    expect(form.rows).toHaveLength(10)
    expect(form.rows.every((row) => row.height === PLAIN_ROW_HEIGHT)).toBe(true)
    expect(form.rows.every((row) => (
      form.columns.every((column) => row.cells[column.id]?.value === '')
    ))).toBe(true)
  })

  it('removes the generated row index when loading a legacy plain table', () => {
    const form = normalizeForm({
      title: '旧普通表格',
      columns: [
        { id: 'row_index', title: '序号', type: 'index', removable: false, editable: false, width: 64 },
        { id: 'title', title: '标题', type: 'text', removable: false, editable: true, width: 220 },
      ],
      rows: [{ id: 'row-1', height: 34, cells: { row_index: { value: '' }, title: { value: '保留内容' } } }],
    })

    expect(form.columns.map((column) => column.id)).toEqual(['title'])
    expect(form.rows[0]?.cells).toEqual({ title: { value: '保留内容', status: undefined, assetPath: undefined, fileName: undefined } })
  })

  it('normalizes ordinary-table legacy rows to one line while retaining the literature height', () => {
    const plain = normalizeForm({
      title: '普通表格',
      columns: [{ id: 'col_text', title: '内容', type: 'text', removable: true, editable: true, width: 180 }],
      rows: [{ id: 'row-1', height: DEFAULT_ROW_HEIGHT, cells: { col_text: { value: '一行内容' } } }],
    })

    expect(plain.rows[0]?.height).toBe(PLAIN_ROW_HEIGHT)
  })

  it('auto-fits persisted ordinary rows from their text instead of retaining stale editor heights', () => {
    const plain = normalizeForm({
      title: '已有普通表格',
      columns: [{ id: 'col_text', title: '内容', type: 'text', removable: true, editable: true, width: 180 }],
      rows: [
        { id: 'empty', height: 56, cells: { col_text: { value: '' } } },
        { id: 'single', height: 56, cells: { col_text: { value: '一行内容' } } },
        { id: 'three-lines', height: 112, cells: { col_text: { value: '第一行\n第二行\n第三行' } } },
      ],
    })

    expect(plain.rows.map((row) => row.height)).toEqual([PLAIN_ROW_HEIGHT, PLAIN_ROW_HEIGHT, 73])
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
    const customColumn = createCustomColumn('是否精读', 'boolean', '依据方法部分判断是否需要精读')
    const added = addColumn(form, customColumn, 2)

    expect(added.columns[2]?.id).toBe(customColumn.id)
    expect(added.columns[2]?.description).toBe('依据方法部分判断是否需要精读')
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

  it('persists bounded row and column dimensions', () => {
    const form = createDefaultLiteratureForm()
    const resized = resizeRow(resizeColumn(form, 'title', 320), form.rows[0]!.id, 180)
    const bounded = resizeRow(resizeColumn(resized, 'title', 1), form.rows[0]!.id, 1)

    expect(resized.columns.find((column) => column.id === 'title')?.width).toBe(320)
    expect(resized.rows[0]?.height).toBe(180)
    expect(bounded.columns.find((column) => column.id === 'title')?.width).toBe(MIN_COLUMN_WIDTH)
    expect(bounded.rows[0]?.height).toBe(MIN_ROW_HEIGHT)
    expect(normalizeForm(bounded).rows[0]?.height).toBe(MIN_ROW_HEIGHT)
  })

  it('uses the 15-line default for missing and legacy row heights', () => {
    const form = createDefaultLiteratureForm()
    const normalized = normalizeForm({
      ...form,
      rows: [
        { ...form.rows[0]!, height: undefined },
        { ...form.rows[0]!, id: 'legacy', height: 112 },
      ],
    })

    expect(normalized.rows.map((row) => row.height)).toEqual([DEFAULT_ROW_HEIGHT, DEFAULT_ROW_HEIGHT])
  })

  it('inserts uploaded images at the Markdown caret', () => {
    expect(insertMarkdownImage('前文后文', 2, 'figure 1.png', 'assets/figure 1.png')).toEqual({
      value: '前文\n![figure 1.png](assets/figure%201.png)\n后文',
      cursor: 42,
    })
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
    expect(markdown).toContain('| 序号 | 文献内容 | 图表 | 标题 |')
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
      columns: [form.columns[0]!, form.columns[1]!, form.columns[4]!, form.columns[3]!, form.columns[2]!],
    })

    expect(reordered.columns.map((column) => column.id).slice(0, 5)).toEqual([
      'row_index',
      'literature_file',
      'title',
      'figures',
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
