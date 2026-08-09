/*
 * Smart literature table domain helpers.
 *
 * Usage:
 * SmartFormsView imports these pure helpers to create the default research
 * literature table, edit cells, filter rows, and export stable CSV/Markdown.
 */

export type SmartColumnType =
  | 'index'
  | 'file'
  | 'readonly_text'
  | 'text'
  | 'smart_text'
  | 'tag'
  | 'smart_tag'
  | 'boolean'
  | 'star'
  | 'date'

export type SmartCellStatus = 'idle' | 'pending' | 'ready' | 'failed'

export interface SmartColumn {
  /** Stable column id used by row cells and export logic. */
  id: string
  /** Header text displayed in the editable table. */
  title: string
  /** Column behavior and editor widget type. */
  type: SmartColumnType
  /** Whether the user can remove this column from the table. */
  removable: boolean
  /** Whether this column can be edited directly. */
  editable: boolean
  /** Width in pixels for a predictable spreadsheet-like layout. */
  width: number
  /** Optional choices used by tag, smart tag, and boolean-like columns. */
  options?: string[]
  /** Soft background class used to visually distinguish smart analysis fields. */
  tone?: 'blue' | 'green' | 'amber' | 'rose' | 'violet' | 'neutral'
}

export interface SmartCell {
  /** User-visible cell value. */
  value: string
  /** Generation lifecycle for smart cells. */
  status?: SmartCellStatus
  /** Relative knowledge path for uploaded literature assets. */
  assetPath?: string
  /** Original uploaded file name. */
  fileName?: string
}

export interface SmartRow {
  /** Stable row id. */
  id: string
  /** Cell map keyed by column id. */
  cells: Record<string, SmartCell>
}

export interface SmartLiteratureForm {
  /** Schema version for future migrations. */
  version: 1
  /** Display name. */
  title: string
  /** Last edited ISO timestamp. */
  updatedAt: string
  /** Column schema. */
  columns: SmartColumn[]
  /** Row data. */
  rows: SmartRow[]
}

export const BUILTIN_COLUMNS: SmartColumn[] = [
  { id: 'paper_type', title: '文献类型', type: 'smart_tag', removable: true, editable: true, width: 200, options: ['研究论文', '综述论文', '方法论文', '病例报告'], tone: 'green' },
  { id: 'rating', title: '重要性', type: 'star', removable: true, editable: true, width: 150 },
  { id: 'reading_progress', title: '阅读进度', type: 'tag', removable: true, editable: true, width: 180, options: ['未读', '已读', '阅读中'] },
  { id: 'keywords', title: '关键词', type: 'smart_text', removable: true, editable: true, width: 180, tone: 'violet' },
  { id: 'abstract', title: '摘要', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'blue' },
  { id: 'journal', title: '期刊', type: 'smart_text', removable: true, editable: true, width: 170, tone: 'amber' },
  { id: 'authors', title: '作者', type: 'smart_text', removable: true, editable: true, width: 180, tone: 'green' },
  { id: 'year', title: '年份', type: 'smart_text', removable: true, editable: true, width: 100, tone: 'neutral' },
  { id: 'why', title: '研究背景(why)', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'rose' },
  { id: 'what', title: '研究内容(what)', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'green' },
  { id: 'how', title: '研究方法(how)', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'violet' },
  { id: 'result', title: '研究结果', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'amber' },
  { id: 'innovation', title: '创新点', type: 'smart_text', removable: true, editable: true, width: 240, tone: 'blue' },
  { id: 'limitations', title: '局限性', type: 'smart_text', removable: true, editable: true, width: 240, tone: 'rose' },
  { id: 'future_work', title: '未来展望', type: 'smart_text', removable: true, editable: true, width: 240, tone: 'violet' },
  { id: 'doi', title: 'DOI', type: 'smart_text', removable: true, editable: true, width: 180, tone: 'neutral' },
  { id: 'url', title: 'URL', type: 'smart_text', removable: true, editable: true, width: 200, tone: 'neutral' },
]

const REQUIRED_COLUMNS: SmartColumn[] = [
  { id: 'row_index', title: '序号', type: 'index', removable: false, editable: false, width: 64 },
  { id: 'literature_file', title: '文献上传', type: 'file', removable: true, editable: false, width: 168 },
  { id: 'literature_content', title: '文献内容', type: 'readonly_text', removable: true, editable: false, width: 240 },
  { id: 'title', title: '标题', type: 'smart_text', removable: false, editable: true, width: 230, tone: 'blue' },
]

/** Separator between multiple tags inside a tag-like cell value. */
const TAG_SEPARATOR = ';'

/** Splits a tag cell value into trimmed, non-empty tags. */
export function splitTags(value: string): string[] {
  return value.split(TAG_SEPARATOR).map((tag) => tag.trim()).filter(Boolean)
}

/** Joins tags into a single cell value, dropping blanks and duplicates in order. */
export function joinTags(tags: string[]): string {
  const seen = new Set<string>()
  return tags
    .map((tag) => tag.trim())
    .filter((tag) => {
      if (!tag || seen.has(tag)) return false
      seen.add(tag)
      return true
    })
    .join(`${TAG_SEPARATOR} `)
}

function createRowId(): string {
  return `row_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`
}

function createCell(column: SmartColumn, value = ''): SmartCell {
  return {
    value: column.id === 'reading_progress' && !value ? '未读' : value,
    status: column.type === 'smart_text' || column.type === 'smart_tag' ? 'idle' : undefined,
  }
}

export function createEmptyRow(columns: SmartColumn[]): SmartRow {
  return {
    id: createRowId(),
    cells: Object.fromEntries(columns.map((column) => [column.id, createCell(column)])),
  }
}

export function createDefaultLiteratureForm(title = '未命名表格'): SmartLiteratureForm {
  const columns = REQUIRED_COLUMNS
  return {
    version: 1,
    title,
    updatedAt: new Date().toISOString(),
    columns,
    rows: [createEmptyRow(columns)],
  }
}

export function normalizeForm(raw: Partial<SmartLiteratureForm> | null | undefined): SmartLiteratureForm {
  const fallback = createDefaultLiteratureForm()
  const sourceColumns = (Array.isArray(raw?.columns) && raw.columns.length ? raw.columns : fallback.columns)
    .map((column) => {
      if (column.id === 'literature_file') return { ...column, title: '文献上传', removable: true, editable: false }
      if (column.id === 'literature_content') return { ...column, removable: true, editable: false }
      if (column.id === 'title') return { ...column, removable: false }
      if (column.id === 'reading_progress') return { ...column, options: ['未读', '已读', '阅读中'] }
      if (column.id === 'rating') return { ...column, title: '重要性' }
      return column
    })
  const hasLiteratureSource = sourceColumns.some((column) => column.id === 'literature_file' || column.id === 'literature_content')
  const requiredColumnIds = hasLiteratureSource
    ? ['row_index', 'literature_file', 'literature_content', 'title']
    : ['row_index', 'title']
  const requiredColumns = requiredColumnIds
    .map((columnId) => sourceColumns.find((column) => column.id === columnId) ?? fallback.columns.find((column) => column.id === columnId))
    .filter(Boolean) as SmartColumn[]
  const columns = [
    ...sourceColumns,
    ...requiredColumns.filter((column) => !sourceColumns.some((sourceColumn) => sourceColumn.id === column.id)),
  ]
  const normalizedColumns = hasLiteratureSource
    ? columns
    : columns.map((column) => column.type === 'smart_text'
      ? { ...column, type: 'text' as const }
      : column.type === 'smart_tag'
        ? { ...column, type: 'tag' as const }
        : column)
  const rows = Array.isArray(raw?.rows) ? raw.rows : fallback.rows
  return {
    version: 1,
    title: raw?.title || fallback.title,
    updatedAt: raw?.updatedAt || fallback.updatedAt,
    columns,
    rows: rows.map((row) => ({
      id: row.id || createRowId(),
      cells: Object.fromEntries(normalizedColumns.map((column) => {
        const existing = row.cells?.[column.id]
        const value = column.id === 'reading_progress' && (!existing?.value || existing.value === '未阅读') ? '未读' : existing?.value
        return [column.id, existing ? { value: value ?? '', status: existing.status, assetPath: existing.assetPath, fileName: existing.fileName } : createCell(column)]
      })),
    })),
  }
}

export function updateCell(row: SmartRow, column: SmartColumn, value: string): SmartRow {
  return {
    ...row,
    cells: {
      ...row.cells,
      [column.id]: {
        ...row.cells[column.id],
        value,
        status: column.type === 'smart_text' || column.type === 'smart_tag' ? 'ready' : row.cells[column.id]?.status,
      },
    },
  }
}

export function addColumn(form: SmartLiteratureForm, column: SmartColumn, index = form.columns.length): SmartLiteratureForm {
  const nextColumns = [...form.columns]
  nextColumns.splice(Math.max(0, Math.min(index, nextColumns.length)), 0, column)
  return {
    ...form,
    updatedAt: new Date().toISOString(),
    columns: nextColumns,
    rows: form.rows.map((row) => ({
      ...row,
      cells: { ...row.cells, [column.id]: createCell(column) },
    })),
  }
}

export function removeColumn(form: SmartLiteratureForm, columnId: string): SmartLiteratureForm {
  const column = form.columns.find((item) => item.id === columnId)
  if (!column?.removable) return form
  return {
    ...form,
    updatedAt: new Date().toISOString(),
    columns: form.columns.filter((item) => item.id !== columnId),
    rows: form.rows.map((row) => {
      const { [columnId]: _removed, ...cells } = row.cells
      return { ...row, cells }
    }),
  }
}

export function moveColumn(form: SmartLiteratureForm, columnId: string, direction: -1 | 1): SmartLiteratureForm {
  const index = form.columns.findIndex((column) => column.id === columnId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= form.columns.length) return form
  const columns = [...form.columns]
  const [column] = columns.splice(index, 1)
  if (!column) return form
  columns.splice(target, 0, column)
  return { ...form, columns, updatedAt: new Date().toISOString() }
}

export function moveRow(form: SmartLiteratureForm, rowId: string, direction: -1 | 1): SmartLiteratureForm {
  const index = form.rows.findIndex((row) => row.id === rowId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= form.rows.length) return form
  const rows = [...form.rows]
  const [row] = rows.splice(index, 1)
  if (!row) return form
  rows.splice(target, 0, row)
  return { ...form, rows, updatedAt: new Date().toISOString() }
}

export function filterRows(form: SmartLiteratureForm, query: string, tagFilter: string, minRating: number): SmartRow[] {
  const normalizedQuery = query.trim().toLowerCase()
  return form.rows.filter((row) => {
    const matchesQuery = !normalizedQuery || form.columns.some((column) => {
      return (row.cells[column.id]?.value ?? '').toLowerCase().includes(normalizedQuery)
    })
    const matchesTag = !tagFilter || form.columns.some((column) => {
      if (column.type !== 'tag' && column.type !== 'smart_tag') return false
      return splitTags(row.cells[column.id]?.value ?? '').includes(tagFilter)
    })
    const ratingValue = Number(row.cells.rating?.value || 0)
    const matchesRating = !minRating || ratingValue >= minRating
    return matchesQuery && matchesTag && matchesRating
  })
}

function exportableColumns(form: SmartLiteratureForm): SmartColumn[] {
  return form.columns.filter((column) => column.type !== 'file')
}

function escapeCsv(value: string): string {
  if (!/[",\n\r]/.test(value)) return value
  return `"${value.replace(/"/g, '""')}"`
}

export function exportCsv(form: SmartLiteratureForm): string {
  const columns = exportableColumns(form)
  const rows = [
    columns.map((column) => escapeCsv(column.title)).join(','),
    ...form.rows.map((row, rowIndex) => columns.map((column) => {
      const value = column.type === 'index' ? String(rowIndex + 1) : row.cells[column.id]?.value ?? ''
      return escapeCsv(value)
    }).join(',')),
  ]
  return `${rows.join('\n')}\n`
}

function escapeMarkdownCell(value: string): string {
  return value.replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim()
}

export function exportMarkdown(form: SmartLiteratureForm): string {
  const columns = exportableColumns(form)
  const header = `| ${columns.map((column) => escapeMarkdownCell(column.title)).join(' | ')} |`
  const divider = `| ${columns.map(() => '---').join(' | ')} |`
  const rows = form.rows.map((row, rowIndex) => {
    const cells = columns.map((column) => {
      return escapeMarkdownCell(column.type === 'index' ? String(rowIndex + 1) : row.cells[column.id]?.value ?? '')
    })
    return `| ${cells.join(' | ')} |`
  })
  return `${[header, divider, ...rows].join('\n')}\n`
}

export function uniqueTagValues(form: SmartLiteratureForm): string[] {
  const values = new Set<string>()
  form.rows.forEach((row) => {
    form.columns.forEach((column) => {
      if (column.type === 'tag' || column.type === 'smart_tag') {
        splitTags(row.cells[column.id]?.value ?? '').forEach((tag) => values.add(tag))
      }
    })
  })
  return [...values].sort((a, b) => a.localeCompare(b))
}

export function createCustomColumn(title: string, type: SmartColumnType): SmartColumn {
  const safeTitle = title.trim() || '自定义列'
  return {
    id: `col_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
    title: safeTitle,
    type,
    removable: true,
    editable: type !== 'index' && type !== 'readonly_text' && type !== 'file',
    width: type === 'star' ? 140 : type === 'boolean' ? 112 : type === 'tag' || type === 'smart_tag' ? 200 : 180,
    options: type === 'boolean' ? ['是', '否'] : undefined,
    tone: type === 'smart_text' || type === 'smart_tag' ? 'blue' : undefined,
  }
}
