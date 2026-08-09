<!--
  Smart literature forms page.

  Usage:
  Provides a spreadsheet-like research literature table stored under the
  knowledge library forms/ directory. Users can edit typed columns, bind PDF
  assets, filter rows, and export CSV/Markdown without leaving the workspace.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { streamPrompt } from '@/api/agent'
import { createKnowledgeFolder, listKnowledgeFiles, previewKnowledgeFile, readKnowledgeFile, uploadKnowledgeFile } from '@/api/knowledge'
import { getSmartFormDb, listSmartFormsDb, saveSmartFormDb } from '@/api/smartForms'
import IcIcon from '@/components/common/IcIcon.vue'
import { materialFileIconForNode } from '@/components/editor_workspace/materialFileIcons'
import { useSubmenuIntent } from '@/components/editor_workspace/submenuIntent'
import {
  BUILTIN_COLUMNS,
  addColumn,
  createCustomColumn,
  createDefaultLiteratureForm,
  createEmptyRow,
  exportCsv,
  exportMarkdown,
  filterRows,
  moveColumn,
  moveRow,
  joinTags,
  normalizeForm,
  removeColumn,
  splitTags,
  uniqueTagValues,
  updateCell,
  type SmartColumn,
  type SmartColumnType,
  type SmartCell,
  type SmartLiteratureForm,
  type SmartRow,
} from '@/components/smart_forms/smartLiteratureTable'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

defineOptions({ name: 'SmartFormsView' })

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

interface SmartFormEntry {
  /** Database form id. */
  formId: string
  /** Display name. */
  name: string
  /** Attachment folder path relative to the knowledge root. */
  assetDir: string
}

const FORMS_ROOT_DIR = 'forms'
const form = ref<SmartLiteratureForm | null>(null)
const formEntries = ref<SmartFormEntry[]>([])
const activeFormId = ref('')
const activeFormDir = ref('')
const loading = ref(false)
const saving = ref(false)
const query = ref('')
const tagFilter = ref('')
const minRating = ref(0)
const newFormTitle = ref('')
const createFormOpen = ref(false)
const selectedCell = ref<{ rowId: string; columnId: string } | null>(null)
const customColumnTitle = ref('')
const uploadInputByRow = ref<Record<string, HTMLInputElement | null>>({})
const imagePreviewByPath = ref<Record<string, string>>({})
const tagEditorKey = ref('')
const tagDraft = ref('')

type TableContextTarget =
  | { kind: 'table' }
  | { kind: 'column'; columnId: string }
  | { kind: 'row'; rowId: string }
  | { kind: 'cell'; rowId: string; columnId: string }

type TableClipboard =
  | { kind: 'cell'; cell: SmartCell }
  | { kind: 'row'; cells: Record<string, SmartCell> }
  | { kind: 'column'; values: Record<string, SmartCell> }

const tableContextTarget = ref<TableContextTarget | null>(null)
const tableContextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
const tableContextSubmenu = ref('')
const tableContextSubmenuRefs: Record<string, HTMLElement | null> = {}
const tableClipboard = ref<TableClipboard | null>(null)
const {
  openSubmenu: openTableSubmenu,
  keepSubmenuOpen: keepTableSubmenuOpen,
  scheduleSubmenuClose: scheduleTableSubmenuClose,
} = useSubmenuIntent(tableContextSubmenu)

const visibleRows = computed(() => form.value ? filterRows(form.value, query.value, tagFilter.value, minRating.value) : [])
const tagFilters = computed(() => form.value ? uniqueTagValues(form.value) : [])
const rowCountLabel = computed(() => form.value ? `${visibleRows.value.length} / ${form.value.rows.length} 条记录` : '0 / 0 条记录')
const activeFormStorageLabel = computed(() => activeFormId.value ? `SQLite: smart_forms/${activeFormId.value}` : '')
const activeFormCsvFile = computed(() => form.value ? `${form.value.title}.csv` : '')
const activeFormAssetDir = computed(() => activeFormDir.value ? `${activeFormDir.value}/assets` : '')
const updatedAtLabel = computed(() => form.value ? new Date(form.value.updatedAt).toLocaleString() : '')
const hasUserId = computed(() => Boolean(settingsStore.profile.userId))

const customColumnTypes: { value: SmartColumnType; label: string }[] = [
  { value: 'text', label: '文本' },
  { value: 'smart_text', label: '智能文本' },
  { value: 'tag', label: '标签' },
  { value: 'smart_tag', label: '智能标签' },
  { value: 'boolean', label: '是/否' },
  { value: 'star', label: '星级' },
  { value: 'date', label: '日期' },
]

onMounted(() => {
  void loadForm()
})

onBeforeUnmount(() => {
  closeTableContextMenu()
})

async function loadForm(): Promise<void> {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    let entries = await listSmartForms()
    if (!entries.length) {
      entries = await importLegacySmartForms()
    }
    formEntries.value = entries
    if (!entries.length) {
      form.value = null
      activeFormId.value = ''
      activeFormDir.value = ''
      return
    }
    await openForm(entries[0]!)
  } catch (error) {
    workspaceStore.showToast(`读取智能表格失败 - ${errorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

/** Loads user-created smart forms from the database. */
async function listSmartForms(): Promise<SmartFormEntry[]> {
  if (!settingsStore.profile.userId) return []
  const entries = await listSmartFormsDb(settingsStore.profile.userId)
  return entries.map((entry) => ({
    formId: entry.form_id,
    name: entry.title,
    assetDir: entry.asset_dir,
  }))
}

/** Imports legacy smart-form JSON files once when the database is empty. */
async function importLegacySmartForms(): Promise<SmartFormEntry[]> {
  if (!settingsStore.profile.userId) return []
  const response = await listKnowledgeFiles(settingsStore.profile.userId)
  const formsRoot = response.tree.find((node) => node.isDir && node.path === FORMS_ROOT_DIR)
  const legacyDirs = (formsRoot?.children ?? []).filter((node) => node.isDir)
  if (!legacyDirs.length) return []
  for (const node of legacyDirs) {
    try {
      const legacy = await readKnowledgeFile(settingsStore.profile.userId, `${node.path}/form.json`)
      const legacyForm = normalizeForm(JSON.parse(legacy.content) as SmartLiteratureForm)
      await saveSmartFormDb({
        user_id: settingsStore.profile.userId,
        asset_dir: node.path,
        form: legacyForm,
      })
    } catch {
      // Ignore invalid legacy folders; database storage is the source of truth after import.
    }
  }
  return listSmartForms()
}

/** Opens an existing smart form from the database. */
async function openForm(entry: SmartFormEntry): Promise<void> {
  if (!settingsStore.profile.userId) return
  try {
    const response = await getSmartFormDb(settingsStore.profile.userId, entry.formId)
    form.value = normalizeForm(response.form)
    activeFormId.value = response.form_id
    activeFormDir.value = response.asset_dir || entry.assetDir
    selectedCell.value = null
    await loadImagePreviews()
  } catch (error) {
    workspaceStore.showToast(`打开表格失败 - ${errorMessage(error)}`)
  }
}

/** Opens a table selected from the database forms list. */
function openFormById(formId: string): void {
  const entry = formEntries.value.find((item) => item.formId === formId)
  if (entry) void openForm(entry)
}

/** Creates a user-named table and persists its initial state in the database. */
async function createSmartForm(): Promise<void> {
  if (!settingsStore.profile.userId) return
  const title = newFormTitle.value.trim()
  if (!title) {
    workspaceStore.showToast('请输入表名')
    return
  }
  const dir = uniqueFormDir(title)
  try {
    await createFolderIfMissing(FORMS_ROOT_DIR)
    await createFolderIfMissing(dir)
    await createFolderIfMissing(`${dir}/assets`)
    form.value = createDefaultLiteratureForm(title)
    activeFormId.value = ''
    activeFormDir.value = dir
    await persistForm(false)
    formEntries.value = await listSmartForms()
    newFormTitle.value = ''
    createFormOpen.value = false
    workspaceStore.showToast('表格已创建')
  } catch (error) {
    workspaceStore.showToast(`创建表格失败 - ${errorMessage(error)}`)
  }
}

/** Creates a filesystem-safe, collision-resistant folder path for a user table name. */
function uniqueFormDir(title: string): string {
  const base = title
    .replace(/[\\/:*?"<>|#%&{}$!'@+`=\s]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || 'table'
  const existingDirs = new Set(formEntries.value.map((entry) => entry.assetDir))
  let candidate = `${FORMS_ROOT_DIR}/${base}`
  let index = 2
  while (existingDirs.has(candidate)) {
    candidate = `${FORMS_ROOT_DIR}/${base}-${index}`
    index += 1
  }
  return candidate
}

async function saveForm(): Promise<void> {
  await persistForm(true)
}

async function persistForm(showSuccessToast: boolean): Promise<void> {
  if (!settingsStore.profile.userId || !form.value || !activeFormDir.value) return
  saving.value = true
  try {
    await ensureFormFolders()
    form.value = { ...form.value, updatedAt: new Date().toISOString() }
    const response = await saveSmartFormDb({
      user_id: settingsStore.profile.userId,
      form_id: activeFormId.value || undefined,
      asset_dir: activeFormDir.value,
      form: form.value,
    })
    activeFormId.value = response.form_id
    activeFormDir.value = response.asset_dir
    form.value = normalizeForm(response.form)
    if (showSuccessToast) {
      workspaceStore.showToast('智能表格已保存')
    }
  } catch (error) {
    workspaceStore.showToast(`保存失败 - ${errorMessage(error)}`)
  } finally {
    saving.value = false
  }
}

async function ensureFormFolders(): Promise<void> {
  if (!settingsStore.profile.userId || !activeFormDir.value) return
  await createFolderIfMissing(FORMS_ROOT_DIR)
  await createFolderIfMissing(activeFormDir.value)
  await createFolderIfMissing(activeFormAssetDir.value)
}

async function createFolderIfMissing(path: string): Promise<void> {
  try {
    await createKnowledgeFolder(settingsStore.profile.userId, path)
  } catch {
    // Existing folders are fine; the backend returns an error instead of a no-op.
  }
}

function addRowAt(rowId: string | undefined, direction: -1 | 1): void {
  if (!form.value) return
  const index = rowId ? form.value.rows.findIndex((row) => row.id === rowId) : form.value.rows.length - 1
  const insertionIndex = Math.max(0, index + (direction > 0 ? 1 : 0))
  const rows = [...form.value.rows]
  rows.splice(insertionIndex, 0, createEmptyRow(form.value.columns))
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows,
  }
}

function deleteRecord(rowId: string): void {
  if (!form.value) return
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows: form.value.rows.filter((row) => row.id !== rowId),
  }
}

function editCell(row: SmartRow, column: SmartColumn, value: string): void {
  if (!form.value) return
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows: form.value.rows.map((item) => item.id === row.id ? updateCell(item, column, value) : item),
  }
}

function setRating(row: SmartRow, column: SmartColumn, rating: number): void {
  editCell(row, column, String(rating))
}

function addColumnAt(column: SmartColumn, direction: -1 | 1): void {
  if (!form.value) return
  if (form.value.columns.some((item) => item.id === column.id)) {
    workspaceStore.showToast('该内置列已存在')
    return
  }
  const targetColumnId = tableContextTarget.value && 'columnId' in tableContextTarget.value
    ? tableContextTarget.value.columnId
    : undefined
  const targetIndex = targetColumnId
    ? form.value.columns.findIndex((item) => item.id === targetColumnId)
    : form.value.columns.length
  const insertionIndex = Math.max(0, targetIndex + (direction > 0 ? 1 : 0))
  form.value = addColumn(form.value, { ...column }, insertionIndex)
}

function addCustomColumnAt(type: SmartColumnType, direction: -1 | 1): void {
  if (!form.value) return
  const targetColumnId = tableContextTarget.value && 'columnId' in tableContextTarget.value
    ? tableContextTarget.value.columnId
    : undefined
  const targetIndex = targetColumnId
    ? form.value.columns.findIndex((item) => item.id === targetColumnId)
    : form.value.columns.length
  form.value = addColumn(form.value, createCustomColumn(customColumnTitle.value, type), Math.max(0, targetIndex + (direction > 0 ? 1 : 0)))
  customColumnTitle.value = ''
}

function removeColumnById(columnId: string): void {
  if (!form.value) return
  form.value = removeColumn(form.value, columnId)
}

function moveColumnById(columnId: string, direction: -1 | 1): void {
  if (!form.value) return
  form.value = moveColumn(form.value, columnId, direction)
}

function moveRowById(rowId: string, direction: -1 | 1): void {
  if (!form.value) return
  form.value = moveRow(form.value, rowId, direction)
}

function setTableContextSubmenuRef(key: string, element: unknown): void {
  tableContextSubmenuRefs[key] = element instanceof HTMLElement ? element : null
}

function handleTableSubmenuLeave(key: string, event: MouseEvent): void {
  const parent = event.currentTarget
  if (parent instanceof HTMLElement) {
    scheduleTableSubmenuClose(key, event, parent, tableContextSubmenuRefs[key] ?? null)
  }
}

function openTableContextMenu(target: TableContextTarget, event: MouseEvent): void {
  closeTagEditor()
  tableContextTarget.value = target
  tableContextSubmenu.value = ''
  tableContextMenuStyle.value = {
    left: `${event.clientX}px`,
    top: `${event.clientY}px`,
  }
}

function closeTableContextMenu(): void {
  tableContextTarget.value = null
  tableContextSubmenu.value = ''
}

function closeFloatingMenus(): void {
  closeTableContextMenu()
  closeTagEditor()
}

function addNewRow(): void {
  addRowAt(undefined, 1)
}

const TAG_COLORS = ['#7c5cfc', '#eb2463', '#26a269', '#2f88d5', '#e2a72e', '#0ea5b6']

/** Stable tag color derived from the tag text, independent of the theme primary color. */
function tagColor(value: string): string {
  let hash = 0
  for (const ch of value) hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return TAG_COLORS[hash % TAG_COLORS.length]!
}

function tagPillStyle(value: string): Record<string, string> {
  const color = tagColor(value)
  return {
    background: `color-mix(in srgb, ${color} 16%, var(--color-surface-raised))`,
    color,
  }
}

function tagKey(rowId: string, columnId: string): string {
  return `${rowId}:${columnId}`
}

function isTagEditorOpen(rowId: string, columnId: string): boolean {
  return tagEditorKey.value === tagKey(rowId, columnId)
}

function openTagEditor(row: SmartRow, column: SmartColumn): void {
  const key = tagKey(row.id, column.id)
  if (tagEditorKey.value === key) {
    closeTagEditor()
    return
  }
  tagEditorKey.value = key
  tagDraft.value = ''
}

function closeTagEditor(): void {
  tagEditorKey.value = ''
  tagDraft.value = ''
}

function cellTags(row: SmartRow, column: SmartColumn): string[] {
  return splitTags(row.cells[column.id]?.value ?? '')
}

function updateTags(row: SmartRow, column: SmartColumn, tags: string[]): void {
  editCell(row, column, joinTags(tags))
}

function toggleTag(row: SmartRow, column: SmartColumn, tag: string): void {
  const tags = cellTags(row, column)
  updateTags(row, column, tags.includes(tag) ? tags.filter((item) => item !== tag) : [...tags, tag])
}

function removeTag(row: SmartRow, column: SmartColumn, tag: string): void {
  updateTags(row, column, cellTags(row, column).filter((item) => item !== tag))
}

function addTagFromDraft(row: SmartRow, column: SmartColumn): void {
  const draft = tagDraft.value.trim()
  if (!draft) return
  const tags = cellTags(row, column)
  if (!tags.includes(draft)) updateTags(row, column, [...tags, draft])
  tagDraft.value = ''
}

function isTagSelected(row: SmartRow, column: SmartColumn, tag: string): boolean {
  return cellTags(row, column).includes(tag)
}

function contextColumn(): SmartColumn | undefined {
  const target = tableContextTarget.value
  if (!form.value || !target || (target.kind !== 'column' && target.kind !== 'cell')) return undefined
  return form.value.columns.find((column) => column.id === target.columnId)
}

function contextRow(): SmartRow | undefined {
  const target = tableContextTarget.value
  if (!form.value || !target || (target.kind !== 'row' && target.kind !== 'cell')) return undefined
  return form.value.rows.find((row) => row.id === target.rowId)
}

function contextCell(): SmartCell | undefined {
  const target = tableContextTarget.value
  if (!target || target.kind !== 'cell') return undefined
  return contextRow()?.cells[target.columnId]
}

function canSmartFillContext(): boolean {
  const target = tableContextTarget.value
  if (!form.value || !target) return false
  if (target.kind === 'cell') return ['smart_text', 'smart_tag'].includes(contextColumn()?.type ?? '')
  if (target.kind === 'column') return ['smart_text', 'smart_tag'].includes(contextColumn()?.type ?? '')
  return form.value.columns.some((column) => column.type === 'smart_text' || column.type === 'smart_tag')
}

function copyTableContext(): void {
  const target = tableContextTarget.value
  if (!target) return
  if (target.kind === 'cell') {
    const cell = contextCell()
    if (cell) tableClipboard.value = { kind: 'cell', cell: { ...cell } }
  } else if (target.kind === 'row') {
    const row = contextRow()
    if (row) tableClipboard.value = { kind: 'row', cells: structuredClone(row.cells) }
  } else if (target.kind === 'column' && form.value) {
    tableClipboard.value = {
      kind: 'column',
      values: Object.fromEntries(form.value.rows.map((row) => [row.id, structuredClone(row.cells[target.columnId] ?? { value: '' })])),
    }
  }
  closeTableContextMenu()
}

function pasteTableContext(): void {
  const target = tableContextTarget.value
  const clipboard = tableClipboard.value
  if (!target || !clipboard || !form.value) return
  if (target.kind === 'cell' && clipboard.kind === 'cell') {
    editCell(contextRow()!, contextColumn()!, clipboard.cell.value)
  } else if (target.kind === 'row' && clipboard.kind === 'row') {
    form.value = {
      ...form.value,
      updatedAt: new Date().toISOString(),
      rows: form.value.rows.map((row) => row.id === target.rowId ? { ...row, cells: structuredClone(clipboard.cells) } : row),
    }
  } else if (target.kind === 'column' && clipboard.kind === 'column') {
    form.value = {
      ...form.value,
      updatedAt: new Date().toISOString(),
      rows: form.value.rows.map((row) => ({
        ...row,
        cells: { ...row.cells, [target.columnId]: structuredClone(clipboard.values[row.id] ?? { value: '' }) },
      })),
    }
  }
  closeTableContextMenu()
}

function clearTableContext(): void {
  const target = tableContextTarget.value
  if (!target || !form.value) return
  if (target.kind === 'cell') {
    editCell(contextRow()!, contextColumn()!, '')
  } else if (target.kind === 'row') {
    form.value = {
      ...form.value,
      updatedAt: new Date().toISOString(),
      rows: form.value.rows.map((row) => row.id === target.rowId ? { ...row, cells: Object.fromEntries(form.value!.columns.map((column) => [column.id, { ...row.cells[column.id], value: '' }])) } : row),
    }
  } else if (target.kind === 'column') {
    form.value = {
      ...form.value,
      updatedAt: new Date().toISOString(),
      rows: form.value.rows.map((row) => ({ ...row, cells: { ...row.cells, [target.columnId]: { ...row.cells[target.columnId], value: '' } } })),
    }
  }
  closeTableContextMenu()
}

async function smartFillTableContext(): Promise<void> {
  const target = tableContextTarget.value
  if (!target || !form.value) return
  if (target.kind === 'cell') {
    await generateSmartCellsForRows([target.rowId], [target.columnId], true)
  } else if (target.kind === 'column') {
    await generateSmartCellsForRows(form.value.rows.map((row) => row.id), [target.columnId], true)
  } else if (target.kind === 'row') {
    await generateSmartCellsForRows([target.rowId], undefined, true)
  } else {
    await generateSmartCellsForRows(form.value.rows.map((row) => row.id), undefined, true)
  }
  closeTableContextMenu()
}

function addContextColumn(column: SmartColumn, direction: -1 | 1): void {
  addColumnAt(column, direction)
  closeTableContextMenu()
}

function addContextCustomColumn(type: SmartColumnType, direction: -1 | 1): void {
  addCustomColumnAt(type, direction)
  closeTableContextMenu()
}

async function generateSmartCells(scope: 'selected' | 'all'): Promise<void> {
  if (!form.value) return
  const target = selectedCell.value
  if (scope === 'selected') {
    const column = form.value.columns.find((item) => item.id === target?.columnId)
    if (!target || !column || (column.type !== 'smart_text' && column.type !== 'smart_tag')) {
      workspaceStore.showToast('请选择一个智能列单元格')
      return
    }
  }
  await generateSmartCellsForRows(
    scope === 'all' ? form.value.rows.map((row) => row.id) : [target!.rowId],
    scope === 'selected' ? [target!.columnId] : undefined,
    true,
  )
}

/** Regenerates a single smart cell from the row's extracted literature content. */
async function generateSmartCellsForRows(rowIds: string[], columnIds?: string[], showSuccessToast = false): Promise<void> {
  if (!form.value) return
  const currentForm = form.value
  const smartColumns = currentForm.columns.filter((column) => {
    const isSmart = column.type === 'smart_text' || column.type === 'smart_tag'
    return isSmart && (!columnIds || columnIds.includes(column.id))
  })
  if (!smartColumns.length || !settingsStore.profile.userId) return
  const rowIdSet = new Set(rowIds)
  form.value = {
    ...currentForm,
    updatedAt: new Date().toISOString(),
    rows: currentForm.rows.map((row) => ({
      ...row,
      cells: Object.fromEntries(currentForm.columns.map((column) => {
        const cell = row.cells[column.id] ?? { value: '' }
        const isTarget = rowIdSet.has(row.id) && smartColumns.some((item) => item.id === column.id)
        return [column.id, isTarget ? { ...cell, status: 'pending' } : cell]
      })),
    })),
  }
  for (const rowId of rowIds) {
    const currentRow = form.value.rows.find((item) => item.id === rowId)
    if (!currentRow) continue
    const literatureContent = currentRow.cells.literature_content?.value.trim() ?? ''
    if (!literatureContent) {
      patchRowCells(rowId, Object.fromEntries(smartColumns.map((column) => [
        column.id,
        { ...currentRow.cells[column.id], value: '', status: 'failed' },
      ])))
      continue
    }
    try {
      const values = await generateStructuredValues(literatureContent, smartColumns)
      patchRowCells(rowId, Object.fromEntries(smartColumns.map((column) => [
        column.id,
        {
          ...currentRow.cells[column.id],
          value: String(values[column.id] ?? '').trim(),
          status: values[column.id] === undefined ? 'failed' : 'ready',
        },
      ])))
    } catch (error) {
      patchRowCells(rowId, Object.fromEntries(smartColumns.map((column) => [
        column.id,
        { ...currentRow.cells[column.id], value: currentRow.cells[column.id]?.value ?? '', status: 'failed' },
      ])))
      workspaceStore.showToast(`智能填充失败 - ${errorMessage(error)}`)
    }
  }
  await persistForm(false)
  if (showSuccessToast) {
    workspaceStore.showToast('智能列已生成')
  }
}

function setUploadRef(rowId: string, element: unknown): void {
  uploadInputByRow.value[rowId] = element instanceof HTMLInputElement ? element : null
}

function openUpload(rowId: string): void {
  uploadInputByRow.value[rowId]?.click()
}

async function uploadLiterature(row: SmartRow, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !settingsStore.profile.userId || !form.value) return
  try {
    await ensureFormFolders()
    const result = await uploadKnowledgeFile(settingsStore.profile.userId, file, activeFormAssetDir.value, false, 'rename') as {
      uploaded_path?: string
      knowledge_dir?: string
    }
    const assetPath = relativeUploadedPath(result.uploaded_path ?? '', result.knowledge_dir ?? settingsStore.profile.knowledgeDir)
    if (assetPath && isImageFile(file.name)) {
      await loadImagePreview(assetPath)
    }
    patchRowCells(row.id, {
      literature_file: { value: file.name, fileName: file.name, assetPath },
      literature_content: {
        value: '正在灌库并提取文献内容...',
        status: 'pending',
      },
    })
    if (assetPath) {
      await workspaceStore.ingestFile({
        name: file.name,
        path: assetPath,
        isDir: false,
        indexStatus: 'dirty',
      })
    }
    const content = assetPath ? await extractUploadedLiteratureContent(assetPath) : ''
    patchRowCells(row.id, {
      literature_content: content
        ? { value: content, status: 'ready' }
        : { value: '文献已入库，但暂未取得可显示文本。请检查文件是否为扫描件或 OCR 设置。', status: 'failed' },
    })
    if (content) {
      await generateSmartCellsForRows([row.id])
    }
    await persistForm(false)
    await workspaceStore.loadKnowledgeTree()
    workspaceStore.showToast('文献已上传并完成内容回填')
  } catch (error) {
    patchRowCells(row.id, {
      literature_content: { value: `上传或灌库失败: ${errorMessage(error)}`, status: 'failed' },
    })
    workspaceStore.showToast(`上传失败 - ${errorMessage(error)}`)
  }
}

async function loadImagePreviews(): Promise<void> {
  const imagePaths = form.value?.rows
    .map((row) => row.cells.literature_file?.assetPath || '')
    .filter((path) => path && isImageFile(path) && imagePreviewByPath.value[path] === undefined) ?? []
  for (const path of imagePaths) {
    await loadImagePreview(path)
  }
}

async function loadImagePreview(path: string): Promise<void> {
  if (!settingsStore.profile.userId || imagePreviewByPath.value[path] !== undefined) return
  try {
    const preview = await previewKnowledgeFile(settingsStore.profile.userId, path)
    imagePreviewByPath.value = { ...imagePreviewByPath.value, [path]: preview.data_url || preview.raw_url || '' }
  } catch {
    imagePreviewByPath.value = { ...imagePreviewByPath.value, [path]: '' }
  }
}

function isImageFile(fileName: string): boolean {
  return /\.(avif|gif|jpe?g|png|webp)$/i.test(fileName)
}

function fileIconForCell(fileName: string) {
  return materialFileIconForNode({ name: fileName, path: fileName, isDir: false })
}

function patchRowCells(rowId: string, cells: Record<string, SmartCell>): void {
  if (!form.value) return
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows: form.value.rows.map((item) => item.id === rowId ? {
      ...item,
      cells: {
        ...item.cells,
        ...Object.fromEntries(Object.entries(cells).map(([columnId, cell]) => [
          columnId,
          { ...item.cells[columnId], ...cell },
        ])),
      },
    } : item),
  }
}

async function extractUploadedLiteratureContent(assetPath: string): Promise<string> {
  if (!settingsStore.profile.userId) return ''
  try {
    const preview = await previewKnowledgeFile(settingsStore.profile.userId, assetPath)
    const content = [preview.content, preview.render_content, preview.message]
      .find((value) => typeof value === 'string' && value.trim())
    if (content) return normalizeLiteratureContent(content)
  } catch {
    // Fall through to direct text read for editable text/markdown uploads.
  }
  try {
    const response = await readKnowledgeFile(settingsStore.profile.userId, assetPath)
    return normalizeLiteratureContent(response.content)
  } catch {
    return ''
  }
}

function normalizeLiteratureContent(content: string): string {
  return content.replace(/\r\n/g, '\n').trim().slice(0, 12000)
}

async function generateStructuredValues(literatureContent: string, columns: SmartColumn[]): Promise<Record<string, string>> {
  const prompt = [
    '你是科研文献表格的结构化抽取器。只输出一个 JSON 对象,不要输出 Markdown 或解释。',
    'JSON 的 key 必须使用给定列 id,value 必须是字符串。无法确定时返回空字符串。',
    '智能标签列如果有 options,优先从 options 中选择一个最贴切的标签。',
    '',
    '需要填充的列:',
    JSON.stringify(columns.map((column) => ({
      id: column.id,
      title: column.title,
      type: column.type,
      options: column.options ?? [],
    })), null, 2),
    '',
    '文献内容:',
    literatureContent.slice(0, 16000),
  ].join('\n')
  let raw = ''
  const sessionId = `smart-form-${Date.now().toString(36)}`
  try {
    for await (const chunk of streamPrompt(settingsStore.profile.userId, sessionId, prompt, {
      agentMode: 'simple',
      agentAccessMode: 'readonly',
    })) {
      if (typeof chunk.content === 'string') {
        raw += chunk.content
      }
      if (typeof chunk.final_output === 'string') {
        raw += chunk.final_output
      }
    }
  } catch {
    return extractStructuredFallback(literatureContent, columns)
  }
  const parsed = parseJsonObject(raw)
  return Object.keys(parsed).length ? parsed : extractStructuredFallback(literatureContent, columns)
}

/** Parses the agent's JSON-only answer without throwing on empty or noisy output. */
function parseJsonObject(text: string): Record<string, string> {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1]
  const source = fenced ?? text
  const candidate = findFirstJsonObject(source)
  if (!candidate) return {}
  try {
    const parsed = JSON.parse(candidate) as Record<string, unknown>
    return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, value == null ? '' : String(value)]))
  } catch {
    return {}
  }
}

/** Returns the first complete top-level JSON object from a noisy stream buffer. */
function findFirstJsonObject(text: string): string {
  const start = text.indexOf('{')
  if (start < 0) return ''
  let depth = 0
  let inString = false
  let escaped = false
  for (let index = start; index < text.length; index += 1) {
    const char = text.charAt(index)
    if (escaped) {
      escaped = false
      continue
    }
    if (char === '\\') {
      escaped = inString
      continue
    }
    if (char === '"') {
      inString = !inString
      continue
    }
    if (inString) continue
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return text.slice(start, index + 1)
  }
  return ''
}

/** Builds conservative values from the extracted document text when the model stream is invalid. */
function extractStructuredFallback(literatureContent: string, columns: SmartColumn[]): Record<string, string> {
  return Object.fromEntries(columns.map((column) => [column.id, extractStructuredFallbackValue(literatureContent, column)]))
}

/** Extracts common literature fields using document headings and stable regexes. */
function extractStructuredFallbackValue(literatureContent: string, column: SmartColumn): string {
  const key = `${column.id} ${column.title}`.toLowerCase()
  if (key.includes('title') || key.includes('标题')) return extractFallbackTitle(literatureContent)
  if (key.includes('keyword') || key.includes('关键词')) return extractFallbackKeywords(literatureContent)
  if (key.includes('doi')) return extractFirstMatch(literatureContent, /\b10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i)
  if (key.includes('url')) return extractFirstMatch(literatureContent, /https?:\/\/\S+/i)
  if (key.includes('year') || key.includes('年份')) return extractFirstMatch(literatureContent, /\b(?:19|20)\d{2}\b/)
  if (key.includes('abstract') || key.includes('摘要')) return extractFallbackAbstract(literatureContent)
  if (key.includes('journal') || key.includes('期刊')) return extractLabelledLine(literatureContent, /(?:journal|期刊)[:：]\s*(.+)/i)
  if (key.includes('type') || key.includes('类型')) return inferFallbackPaperType(literatureContent, column.options)
  return ''
}

/** Uses the first meaningful non-metadata line as a safe title fallback. */
function extractFallbackTitle(literatureContent: string): string {
  const line = literatureContent.split('\n')
    .map((value) => value.replace(/^#+\s*/, '').trim())
    .find((value) => value && !/^page\s+\d+$/i.test(value) && !/^doi[:：]/i.test(value))
  return trimCellText(line ?? '', 140)
}

/** Extracts explicit keywords first, otherwise returns a short list of frequent terms. */
function extractFallbackKeywords(literatureContent: string): string {
  const labelled = extractLabelledLine(literatureContent, /(?:keywords?|关键词)[:：]\s*(.+)/i)
  if (labelled) return trimCellText(labelled, 120)
  const terms = literatureContent
    .replace(/[^\p{Script=Han}A-Za-z0-9\s-]/gu, ' ')
    .split(/\s+/)
    .map((word) => word.trim())
    .filter((word) => word.length >= 4 && !/^(page|abstract|introduction|references)$/i.test(word))
  return [...new Set(terms)].slice(0, 6).join('; ')
}

/** Pulls a compact abstract block from common English/Chinese headings. */
function extractFallbackAbstract(literatureContent: string): string {
  const match = literatureContent.match(/(?:^|\n)\s*(?:abstract|摘要)\s*[:：]?\s*([\s\S]{40,900}?)(?=\n\s*(?:keywords?|关键词|introduction|引言|references|参考文献)\b|$)/i)
  return trimCellText(match?.[1] ?? '', 360)
}

/** Finds the first labelled line value for metadata-like fields. */
function extractLabelledLine(literatureContent: string, pattern: RegExp): string {
  return trimCellText(literatureContent.match(pattern)?.[1] ?? '', 120)
}

/** Finds and trims the first regex match. */
function extractFirstMatch(literatureContent: string, pattern: RegExp): string {
  return trimCellText(literatureContent.match(pattern)?.[0] ?? '', 120)
}

/** Chooses a compatible paper type option from obvious document cues. */
function inferFallbackPaperType(literatureContent: string, options: string[] | undefined): string {
  const text = literatureContent.toLowerCase()
  const preferred = text.includes('review') || literatureContent.includes('综述')
    ? '综述论文'
    : text.includes('method') || literatureContent.includes('方法')
      ? '方法论文'
      : text.includes('case report') || literatureContent.includes('病例')
        ? '病例报告'
        : '研究论文'
  return options?.includes(preferred) ? preferred : (options?.[0] ?? preferred)
}

/** Normalizes generated text so cells do not grow without bound. */
function trimCellText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1)}…` : normalized
}

function downloadCsv(): void {
  if (!form.value) return
  downloadText(`${form.value.title}.csv`, exportCsv(form.value), 'text/csv;charset=utf-8')
}

function downloadMarkdown(): void {
  if (!form.value) return
  downloadText(`${form.value.title}.md`, exportMarkdown(form.value), 'text/markdown;charset=utf-8')
}

function downloadText(fileName: string, content: string, type: string): void {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

function relativeUploadedPath(uploadedPath: string, knowledgeDir: string): string {
  const normalizedRoot = knowledgeDir.replace(/\\/g, '/').replace(/\/+$/g, '')
  const normalizedPath = uploadedPath.replace(/\\/g, '/')
  if (normalizedPath.startsWith(`${normalizedRoot}/`)) {
    return normalizedPath.slice(normalizedRoot.length + 1)
  }
  return normalizedPath
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请检查后端连接'
}
</script>

<template>
  <section class="smart-forms-view" @click="closeFloatingMenus">
    <header class="forms-header">
      <div class="header-copy">
        <p class="forms-eyebrow">智能表格</p>
        <h1>{{ form?.title || '创建你的第一张表' }}</h1>
      </div>
      <div class="header-actions">
        <select
          v-if="formEntries.length > 1"
          class="form-select"
          :value="activeFormId"
          title="切换表格"
          @change="openFormById(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="entry in formEntries" :key="entry.formId" :value="entry.formId">{{ entry.name }}</option>
        </select>
        <button class="ghost-btn" type="button" title="新建表格" @click="createFormOpen = true">
          <IcIcon name="add" :size="16" />
          <span>新建表格</span>
        </button>
        <details v-if="form" class="export-menu">
          <summary class="ghost-btn" title="导出表格">
            <IcIcon name="download" :size="16" />
            <span>导出</span>
          </summary>
          <div class="export-menu-panel">
            <button type="button" @click="downloadMarkdown">Markdown</button>
            <button type="button" @click="downloadCsv">CSV</button>
          </div>
        </details>
        <button class="primary-btn" type="button" :disabled="saving || !hasUserId || !form" @click="saveForm">
          <IcIcon name="save" :size="16" />
          <span>{{ saving ? '保存中' : '保存' }}</span>
        </button>
      </div>
    </header>

    <div v-if="createFormOpen" class="form-dialog-backdrop" @click.self="createFormOpen = false">
      <form class="form-dialog" role="dialog" aria-modal="true" aria-labelledby="create-form-title" @submit.prevent="createSmartForm">
        <div class="form-dialog-header">
          <div>
            <p class="forms-eyebrow">新建</p>
            <h2 id="create-form-title">创建表格</h2>
          </div>
          <button class="dialog-close" type="button" title="关闭" aria-label="关闭" @click="createFormOpen = false">
            <IcIcon name="close" :size="18" />
          </button>
        </div>
        <label class="dialog-field">
          <span>表格名称</span>
          <input v-model="newFormTitle" autofocus type="text" placeholder="例如：项目文献库" />
        </label>
        <div class="form-dialog-actions">
          <button class="ghost-btn" type="button" @click="createFormOpen = false">取消</button>
          <button class="primary-btn" type="submit">创建表格</button>
        </div>
      </form>
    </div>

    <div v-if="!form" class="form-empty-state">
      <IcIcon name="table-chart" :size="32" />
      <p>还没有表格。输入表名后创建，数据会保存到知识库 forms/ 下。</p>
    </div>

    <div v-if="form" class="forms-toolbar">
      <button class="new-row-btn" type="button" @click.stop="addNewRow">
        <IcIcon name="add" :size="16" />
        <span>新建行</span>
      </button>
      <button class="toolbar-btn" type="button" @click="generateSmartCells('all')">
        <IcIcon name="psychology" :size="16" />
        <span>全表智能填充</span>
      </button>
      <label class="search-box">
        <IcIcon name="search" :size="15" />
        <input v-model="query" type="search" placeholder="搜索全表" />
      </label>
      <select v-model="tagFilter" class="filter-select" title="标签筛选">
        <option value="">全部标签</option>
        <option v-for="tag in tagFilters" :key="tag" :value="tag">{{ tag }}</option>
      </select>
      <select v-model.number="minRating" class="filter-select" title="星级筛选">
        <option :value="0">全部星级</option>
        <option :value="5">5 星</option>
        <option :value="4">4 星以上</option>
        <option :value="3">3 星以上</option>
      </select>
      <span class="row-count">{{ rowCountLabel }}</span>
    </div>

    <div v-if="form" class="table-frame" :class="{ loading }" @contextmenu.prevent.stop="openTableContextMenu({ kind: 'table' }, $event)">
      <table class="smart-table">
        <thead>
          <tr>
            <th
              v-for="(column, columnIndex) in form.columns"
              :key="column.id"
              :class="['tone-' + (column.tone || 'none'), { sticky: column.id === 'row_index' }]"
              :style="{ width: `${column.width}px`, minWidth: `${column.width}px` }"
              @contextmenu.prevent.stop="openTableContextMenu({ kind: 'column', columnId: column.id }, $event)"
            >
              <div class="column-head">
                <span>{{ column.title }}</span>
                <div class="column-actions">
                  <button type="button" title="左移" :disabled="columnIndex === 0" @click="moveColumnById(column.id, -1)">
                    <IcIcon name="arrow-left" :size="13" />
                  </button>
                  <button type="button" title="右移" :disabled="columnIndex === form.columns.length - 1" @click="moveColumnById(column.id, 1)">
                    <IcIcon name="arrow-right" :size="13" />
                  </button>
                  <button type="button" title="删除列" :disabled="!column.removable" @click="removeColumnById(column.id)">
                    <IcIcon name="remove" :size="13" />
                  </button>
                </div>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in visibleRows" :key="row.id">
            <td
              v-for="column in form.columns"
              :key="column.id"
              :data-column-id="column.id"
              :class="['cell', 'tone-' + (column.tone || 'none'), { sticky: column.id === 'row_index', selected: selectedCell?.rowId === row.id && selectedCell?.columnId === column.id }]"
              @click="selectedCell = { rowId: row.id, columnId: column.id }"
              @contextmenu.prevent.stop="column.type === 'index' ? openTableContextMenu({ kind: 'row', rowId: row.id }, $event) : openTableContextMenu({ kind: 'cell', rowId: row.id, columnId: column.id }, $event)"
            >
              <span v-if="column.type === 'index'" class="row-index">{{ rowIndex + 1 }}</span>
              <div v-else-if="column.type === 'file'" class="file-cell">
                <button class="file-picker" type="button" @click="openUpload(row.id)">
                  <img
                    v-if="row.cells[column.id]?.assetPath && isImageFile(row.cells[column.id]?.fileName || row.cells[column.id]?.assetPath || '') && imagePreviewByPath[row.cells[column.id]?.assetPath || '']"
                    class="file-preview-image"
                    :src="imagePreviewByPath[row.cells[column.id]?.assetPath || '']"
                    :alt="row.cells[column.id]?.fileName || '图片文档'"
                  />
                  <img
                    v-else-if="row.cells[column.id]?.fileName || row.cells[column.id]?.value"
                    class="file-material-icon"
                    :src="fileIconForCell(row.cells[column.id]?.fileName || row.cells[column.id]?.value || '').src"
                    alt=""
                    aria-hidden="true"
                  />
                  <IcIcon v-else name="upload" :size="24" />
                  <span>{{ row.cells[column.id]?.fileName || row.cells[column.id]?.value || '添加文档' }}</span>
                </button>
                <input
                  :ref="(el) => setUploadRef(row.id, el)"
                  class="hidden-input"
                  type="file"
                  @change="uploadLiterature(row, $event)"
                />
              </div>
              <div
                v-else-if="column.type === 'tag' || column.type === 'smart_tag'"
                class="tag-cell"
                @click.stop="openTagEditor(row, column)"
              >
                <span
                  v-for="tag in cellTags(row, column)"
                  :key="tag"
                  class="tag-pill"
                  :style="tagPillStyle(tag)"
                  @click.stop="openTagEditor(row, column)"
                >
                  <span class="tag-pill-label">{{ tag }}</span>
                  <button type="button" class="tag-pill-action danger" title="删除标签" @click.stop="removeTag(row, column, tag)">
                    <IcIcon name="close" :size="12" />
                  </button>
                </span>
                <button type="button" class="tag-add-button" @click.stop="openTagEditor(row, column)">
                  <IcIcon name="add" :size="13" />
                  <span>{{ cellTags(row, column).length ? '标签' : '添加标签' }}</span>
                </button>
                <div v-if="isTagEditorOpen(row.id, column.id)" class="tag-editor" @click.stop>
                  <div v-if="cellTags(row, column).length" class="tag-editor-selected">
                    <button
                      v-for="tag in cellTags(row, column)"
                      :key="tag"
                      type="button"
                      class="tag-selected-pill"
                      :style="tagPillStyle(tag)"
                      title="移除标签"
                      @click="removeTag(row, column, tag)"
                    >
                      {{ tag }}
                      <IcIcon name="close" :size="10" />
                    </button>
                  </div>
                  <div v-if="column.options?.length" class="tag-option-list">
                    <button
                      v-for="option in column.options"
                      :key="option"
                      type="button"
                      class="tag-option-pill"
                      :class="{ selected: isTagSelected(row, column, option) }"
                      :style="tagPillStyle(option)"
                      @click="toggleTag(row, column, option)"
                    >
                      {{ option }}
                    </button>
                  </div>
                  <div class="tag-editor-input-row">
                    <input
                      v-model="tagDraft"
                      type="text"
                      placeholder="输入标签"
                      @keydown.enter.prevent="addTagFromDraft(row, column)"
                    />
                    <button type="button" title="添加标签" @click="addTagFromDraft(row, column)">
                      <IcIcon name="check" :size="13" />
                    </button>
                  </div>
                </div>
              </div>
              <select
                v-else-if="column.type === 'boolean'"
                :value="row.cells[column.id]?.value || ''"
                @change="editCell(row, column, ($event.target as HTMLSelectElement).value)"
              >
                <option value="">未设置</option>
                <option v-for="option in column.options || []" :key="option" :value="option">{{ option }}</option>
              </select>
              <div v-else-if="column.type === 'star'" class="star-cell">
                <button
                  v-for="rating in 5"
                  :key="rating"
                  type="button"
                  :class="{ active: Number(row.cells[column.id]?.value || 0) >= rating }"
                  @click="setRating(row, column, rating)"
                >
                  ★
                </button>
              </div>
              <input
                v-else-if="column.type === 'date'"
                type="datetime-local"
                :value="row.cells[column.id]?.value || ''"
                @input="editCell(row, column, ($event.target as HTMLInputElement).value)"
              />
              <textarea
                v-else
                :readonly="!column.editable"
                :value="row.cells[column.id]?.value || ''"
                :placeholder="row.cells[column.id]?.status === 'pending' ? '等待结构化 LLM 服务生成' : ''"
                @input="column.editable && editCell(row, column, ($event.target as HTMLTextAreaElement).value)"
              ></textarea>
              <span v-if="row.cells[column.id]?.status === 'pending'" class="status-dot">生成中</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!visibleRows.length" class="empty-state">
        <IcIcon name="table-chart" :size="28" />
        <p>没有符合条件的记录</p>
      </div>
    </div>

    <div
      v-if="tableContextTarget"
      class="table-context-menu"
      :class="{ dark: settingsStore.isDark }"
      :style="tableContextMenuStyle"
      @click.stop
    >
      <div
        class="table-context-submenu-item"
        :class="{ active: tableContextSubmenu.startsWith('add-column') }"
        @mouseenter="openTableSubmenu('add-column')"
        @mouseleave="handleTableSubmenuLeave('add-column', $event)"
      >
        <button type="button"><IcIcon name="view-column" :size="15" /><span>添加列</span><IcIcon name="chevron-right" :size="15" /></button>
        <div
          v-show="tableContextSubmenu.startsWith('add-column')"
          :ref="(element) => setTableContextSubmenuRef('add-column', element)"
          class="table-context-submenu"
          @mouseenter="keepTableSubmenuOpen"
          @mouseleave="handleTableSubmenuLeave('add-column', $event)"
        >
          <div
            v-for="direction in [{ key: 'left', label: '左侧添加', value: -1 }, { key: 'right', label: '右侧添加', value: 1 }]"
            :key="direction.key"
            class="table-context-submenu-item table-context-submenu-level-two"
            :class="{ active: tableContextSubmenu === `add-column-${direction.key}` }"
            @mouseenter="openTableSubmenu(`add-column-${direction.key}`)"
            @mouseleave="handleTableSubmenuLeave(`add-column-${direction.key}`, $event)"
          >
            <button type="button"><IcIcon name="add" :size="15" /><span>{{ direction.label }}</span><IcIcon name="chevron-right" :size="15" /></button>
            <div
              v-show="tableContextSubmenu === `add-column-${direction.key}`"
              :ref="(element) => setTableContextSubmenuRef(`add-column-${direction.key}`, element)"
              class="table-context-submenu table-context-submenu-level-three"
              @mouseenter="keepTableSubmenuOpen"
              @mouseleave="handleTableSubmenuLeave(`add-column-${direction.key}`, $event)"
            >
              <span class="table-context-section-title">内置字段</span>
              <button
                v-for="column in BUILTIN_COLUMNS"
                :key="column.id"
                type="button"
                :disabled="Boolean(form?.columns.some((item) => item.id === column.id))"
                @click="addContextColumn(column, direction.value as -1 | 1)"
              >
                <IcIcon name="view-column" :size="15" /><span>{{ column.title }}</span>
              </button>
              <hr class="table-context-separator" />
              <label class="table-context-input">
                <span>自定义字段名</span>
                <input v-model="customColumnTitle" type="text" placeholder="例如：备注" @click.stop />
              </label>
              <span class="table-context-section-title">字段类型</span>
              <button
                v-for="type in customColumnTypes"
                :key="type.value"
                type="button"
                @click="addContextCustomColumn(type.value, direction.value as -1 | 1)"
              >
                <IcIcon name="add" :size="15" /><span>{{ type.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div
        class="table-context-submenu-item"
        :class="{ active: tableContextSubmenu === 'add-row' }"
        @mouseenter="openTableSubmenu('add-row')"
        @mouseleave="handleTableSubmenuLeave('add-row', $event)"
      >
        <button type="button"><IcIcon name="add" :size="15" /><span>添加行</span><IcIcon name="chevron-right" :size="15" /></button>
        <div
          v-show="tableContextSubmenu === 'add-row'"
          :ref="(element) => setTableContextSubmenuRef('add-row', element)"
          class="table-context-submenu"
          @mouseenter="keepTableSubmenuOpen"
          @mouseleave="handleTableSubmenuLeave('add-row', $event)"
        >
          <button type="button" @click="addRowAt('rowId' in tableContextTarget ? tableContextTarget.rowId : undefined, -1); closeTableContextMenu()"><IcIcon name="arrow-up" :size="15" /><span>在上方添加</span></button>
          <button type="button" @click="addRowAt('rowId' in tableContextTarget ? tableContextTarget.rowId : undefined, 1); closeTableContextMenu()"><IcIcon name="arrow-down" :size="15" /><span>在下方添加</span></button>
        </div>
      </div>

      <hr class="table-context-separator" />
      <button type="button" :disabled="!canSmartFillContext()" @click="smartFillTableContext"><IcIcon name="psychology" :size="15" /><span>智能填充</span></button>
      <button type="button" :disabled="!['cell', 'row', 'column'].includes(tableContextTarget.kind)" @click="copyTableContext"><IcIcon name="copy" :size="15" /><span>复制</span><kbd>Ctrl+C</kbd></button>
      <button type="button" :disabled="!tableClipboard" @click="pasteTableContext"><IcIcon name="paste" :size="15" /><span>粘贴</span><kbd>Ctrl+V</kbd></button>
      <button type="button" :disabled="tableContextTarget.kind === 'table'" @click="clearTableContext"><IcIcon name="remove" :size="15" /><span>清空</span></button>
    </div>

    <footer v-if="form" class="forms-footer">
      <span>存储: {{ activeFormStorageLabel }}</span>
      <span>导出: {{ activeFormCsvFile }}</span>
      <span>更新: {{ updatedAtLabel }}</span>
    </footer>
  </section>
</template>

<style scoped>
.smart-forms-view {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  min-height: 0;
  height: 100%;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
}

.forms-header,
.forms-toolbar,
.forms-footer {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  border-bottom: 0;
  background: var(--color-surface-raised);
}

.forms-header {
  min-height: 44px;
  justify-content: space-between;
  padding: var(--space-8) var(--space-12);
}

.header-copy {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  gap: var(--space-8);
  min-width: 0;
  min-height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  overflow: hidden;
}

.forms-eyebrow {
  margin: 0;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  white-space: nowrap;
}

.header-copy .forms-eyebrow::after {
  margin-left: var(--space-8);
  color: var(--color-text-muted);
  content: ">";
}

.form-dialog .forms-eyebrow {
  margin-bottom: 4px;
}

.forms-header h1 {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: calc(13px * var(--font-scale));
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions,
.column-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.primary-btn,
.ghost-btn,
.toolbar-btn,
.new-row-btn,
.view-tab,
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 28px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.primary-btn {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
  padding: 0 var(--space-10);
}

.ghost-btn,
.toolbar-btn,
.new-row-btn {
  padding: 0 var(--space-8);
}

.new-row-btn {
  background: var(--color-primary);
  color: #ffffff;
}

.toolbar-btn.strong {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.primary-btn:hover,
.ghost-btn:hover,
.toolbar-btn:hover,
.new-row-btn:hover,
.icon-btn:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.new-row-btn:hover {
  background: var(--color-primary-hover, var(--color-primary));
  color: #ffffff;
}

.forms-toolbar {
  position: relative;
  min-height: 44px;
  padding: var(--space-8) var(--space-12);
  flex-wrap: wrap;
}

.search-box {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 180px;
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
}

.search-box input,
.filter-select,
.form-select {
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
}

.search-box input {
  width: 100%;
}

.filter-select {
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 0 var(--space-10);
  background: var(--color-canvas);
}

.form-select,
.new-form-input {
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 0 var(--space-10);
  background: var(--color-canvas);
  color: var(--color-text-secondary);
}

.form-empty-state {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 280px;
  padding: 24px;
  color: var(--color-text-muted);
  background: var(--color-canvas);
  text-align: center;
}

.export-menu {
  position: relative;
}

.export-menu summary {
  list-style: none;
}

.export-menu summary::-webkit-details-marker {
  display: none;
}

.export-menu-panel {
  position: absolute;
  z-index: 20;
  top: calc(100% + 6px);
  right: 0;
  display: grid;
  min-width: 132px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
}

.export-menu-panel button {
  border: 0;
  padding: 8px 10px;
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.export-menu-panel button:hover {
  background: var(--color-selection-blue-soft);
}

.form-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--color-canvas) 68%, transparent);
}

.form-dialog {
  width: min(420px, 100%);
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  box-shadow: var(--shadow-lg);
}

.form-dialog-header,
.form-dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-dialog-header {
  margin-bottom: 20px;
}

.form-dialog h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.dialog-close {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.dialog-field {
  display: grid;
  gap: 7px;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.dialog-field input {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
}

.form-dialog-actions {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 24px;
}

.form-empty-state p {
  max-width: 420px;
  margin: 0;
}

.row-count {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 var(--space-8);
  border-radius: 999px;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.row-count {
  margin-left: auto;
}

.table-context-menu {
  position: fixed;
  z-index: 50;
  display: grid;
  min-width: 252px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #ffffff;
  box-shadow: var(--shadow-lg);
}

.table-context-menu.dark {
  background: #151820;
}

.table-context-menu,
.table-context-submenu {
  color: var(--color-text-secondary);
}

.table-context-submenu {
  position: absolute;
  top: calc(-1 * var(--space-6));
  left: calc(100% + var(--space-8));
  z-index: 1;
  display: grid;
  min-width: 248px;
  box-sizing: border-box;
  overflow: visible;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #ffffff;
  box-shadow: var(--shadow-lg);
}

.table-context-menu.dark .table-context-submenu {
  background: #151820;
}

.table-context-menu button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  column-gap: var(--space-10);
  width: 100%;
  box-sizing: border-box;
  min-height: 30px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  text-align: left;
}

.table-context-menu button:hover:not(:disabled),
.table-context-submenu-item.active > button {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.table-context-menu button:disabled {
  cursor: default;
  opacity: 0.45;
}

.table-context-submenu-item {
  position: relative;
}

.table-context-submenu-item > button {
  width: 100%;
}

.table-context-submenu-level-two {
  position: relative;
}

.table-context-submenu-level-three {
  min-width: 300px;
  max-height: min(620px, calc(100vh - 24px));
  overflow-x: hidden;
  overflow-y: auto;
}

.table-context-menu kbd {
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.table-context-section-title {
  display: block;
  padding: 4px var(--space-8);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.table-context-input {
  display: grid;
  gap: 4px;
  padding: 4px var(--space-8) var(--space-6);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.table-context-input input {
  width: 100%;
  height: 28px;
  box-sizing: border-box;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  font: inherit;
}

.table-context-separator {
  width: 100%;
  margin: var(--space-6) 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.table-frame {
  position: relative;
  min-height: 0;
  overflow: auto;
  background: var(--color-canvas);
}

.smart-table {
  border-collapse: separate;
  border-spacing: 0;
  width: max-content;
  min-width: 100%;
  table-layout: fixed;
}

th,
td {
  border-right: 0;
  border-bottom: 1px solid rgba(127, 127, 127, 0.12);
  vertical-align: top;
}

th {
  position: sticky;
  top: 0;
  z-index: 4;
  height: 34px;
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  font-weight: 500;
}

.column-head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  min-width: 0;
  padding: 0 32px 0 var(--space-12);
}

.column-head > span {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-actions {
  position: absolute;
  top: 50%;
  right: 6px;
  display: flex;
  transform: translateY(-50%);
  opacity: 0;
}

th:hover .column-actions {
  opacity: 1;
}

.column-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
}

.column-actions button:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.cell {
  position: relative;
  height: 112px;
  box-sizing: border-box;
  background: transparent;
}

tbody tr:hover .cell,
tbody tr:hover .cell {
  background: var(--color-selection-blue-soft);
}

.cell.selected {
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.sticky {
  position: sticky;
  left: 0;
  z-index: 3;
}

th.sticky {
  z-index: 6;
}

.row-index {
  display: block;
  padding: 12px;
  color: var(--color-text-muted);
  text-align: center;
}

.cell textarea,
.cell select,
.cell input {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-height: 0;
  resize: none;
  border: 0;
  outline: 0;
  padding: 11px;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  line-height: 1.35;
}

.cell select,
.cell input {
  min-height: 40px;
  height: 40px;
}

.tag-cell {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
  min-height: 100%;
  padding: 12px;
}

.tag-pill,
.tag-add-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 24px;
  border-radius: 999px;
  font-size: calc(12px * var(--font-scale));
}

.tag-pill {
  max-width: 100%;
  padding: 0 4px 0 10px;
  border: 0;
  background: var(--color-surface-active);
  color: var(--color-text-secondary);
}

.tag-pill-label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-add-button {
  padding: 0 10px;
  border: 1px dashed var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.tag-add-button:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text-secondary);
}

.tag-pill-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.tag-pill-action:hover {
  background: color-mix(in srgb, var(--color-text) 10%, transparent);
}

.tag-pill-action.danger:hover {
  background: color-mix(in srgb, var(--color-danger) 14%, transparent);
  color: var(--color-danger);
}

.tag-editor {
  position: absolute;
  top: 42px;
  left: 8px;
  z-index: 12;
  display: grid;
  gap: 8px;
  min-width: 188px;
  max-width: 220px;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-lg);
}

.tag-editor-selected {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.tag-selected-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 24px;
  min-height: 24px;
  padding: 0 8px;
  border: 0;
  border-radius: 999px;
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
}

.tag-editor-input-row {
  display: grid;
  grid-template-columns: 132px 24px;
  gap: 6px;
  justify-content: start;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.tag-editor-input-row input {
  width: 132px;
  height: 24px;
  min-height: 24px;
  box-sizing: border-box;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  outline: 0;
  background: color-mix(in srgb, var(--color-primary) 6%, var(--color-canvas));
  color: var(--color-text);
  font: inherit;
}

.tag-editor-input-row button {
  width: 24px;
  height: 24px;
  min-height: 24px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: var(--color-primary-softer);
  color: var(--color-primary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  text-align: left;
  cursor: pointer;
}

.tag-editor-input-row button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tag-editor-input-row button:hover {
  background: var(--color-primary);
  color: #ffffff;
}

.tag-option-list {
  display: grid;
  grid-template-columns: repeat(2, max-content);
  align-items: start;
  justify-content: start;
  gap: 6px;
  max-height: 140px;
  overflow-x: hidden;
  overflow-y: auto;
}

.tag-option-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 24px;
  min-height: 24px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background: var(--color-surface-active);
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  text-align: center;
  white-space: nowrap;
  cursor: pointer;
}

.tag-option-pill.selected {
  filter: saturate(1.9) brightness(1.18);
}

.tag-option-pill:hover {
  filter: brightness(1.06);
}

.file-cell {
  height: 100%;
  padding: 0;
}

.file-picker {
  display: grid;
  grid-template-rows: 1fr auto;
  align-items: center;
  justify-items: center;
  gap: 5px;
  width: 100%;
  height: 100%;
  padding: 10px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow: hidden;
}

.file-picker:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.file-picker span {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.file-preview-image,
.file-material-icon {
  display: block;
  width: 52px;
  height: 52px;
  object-fit: contain;
}

.file-preview-image {
  border-radius: var(--radius-sm);
  object-fit: cover;
}

.hidden-input {
  display: none;
}

.star-cell {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 12px;
}

.star-cell button {
  border: 0;
  background: transparent;
  color: color-mix(in srgb, var(--color-text-muted) 45%, transparent);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.star-cell button.active {
  color: #f3bd21;
}

.status-dot {
  position: absolute;
  right: 8px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--color-primary-softer);
  color: var(--color-primary);
  font-size: 10px;
}

.tone-blue {
  background: color-mix(in srgb, var(--color-primary) 4%, transparent);
}

.tone-green {
  background: color-mix(in srgb, var(--color-success) 6%, transparent);
}

.tone-amber {
  background: color-mix(in srgb, var(--color-warning) 7%, transparent);
}

.tone-rose {
  background: color-mix(in srgb, var(--color-accent) 5%, transparent);
}

.tone-violet {
  background: color-mix(in srgb, var(--color-primary) 6%, transparent);
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 8px;
  height: 260px;
  color: var(--color-text-muted);
}

.forms-footer {
  min-height: 32px;
  padding: 0 var(--space-12);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

@media (max-width: 760px) {
  .forms-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-copy {
    width: 100%;
  }

  .header-actions,
  .forms-toolbar {
    width: 100%;
    justify-content: flex-start;
  }

  .search-box {
    flex: 1 1 100%;
  }
}
</style>
