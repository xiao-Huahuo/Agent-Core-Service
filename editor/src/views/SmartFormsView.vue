<!--
  Smart literature forms page.

  Usage:
  Provides a spreadsheet-like research literature table stored under the
  knowledge library forms/ directory. Users can edit typed columns, bind PDF
  assets, filter rows, and export CSV/Markdown without leaving the workspace.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { streamPrompt } from '@/api/agent'
import { createKnowledgeFolder, listKnowledgeFiles, previewKnowledgeFile, readKnowledgeFile, uploadKnowledgeFile, writeKnowledgeFile } from '@/api/knowledge'
import IcIcon from '@/components/common/IcIcon.vue'
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
  normalizeForm,
  removeColumn,
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
  /** Table folder name under knowledge/forms. */
  name: string
  /** Table folder path relative to the knowledge root. */
  dir: string
  /** Metadata file path relative to the knowledge root. */
  metaPath: string
}

const FORMS_ROOT_DIR = 'forms'
const form = ref<SmartLiteratureForm | null>(null)
const formEntries = ref<SmartFormEntry[]>([])
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
const customColumnType = ref<SmartColumnType>('text')
const addColumnMenuOpen = ref(false)
const uploadInputByRow = ref<Record<string, HTMLInputElement | null>>({})

const visibleRows = computed(() => form.value ? filterRows(form.value, query.value, tagFilter.value, minRating.value) : [])
const tagFilters = computed(() => form.value ? uniqueTagValues(form.value) : [])
const rowCountLabel = computed(() => form.value ? `${visibleRows.value.length} / ${form.value.rows.length} 条记录` : '0 / 0 条记录')
const activeFormMetaFile = computed(() => activeFormDir.value ? `${activeFormDir.value}/form.json` : '')
const activeFormCsvFile = computed(() => activeFormDir.value ? `${activeFormDir.value}/data.csv` : '')
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

async function loadForm(): Promise<void> {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    const entries = await listSmartForms()
    formEntries.value = entries
    if (!entries.length) {
      form.value = null
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

/** Loads real user-created table folders from knowledge/forms. */
async function listSmartForms(): Promise<SmartFormEntry[]> {
  if (!settingsStore.profile.userId) return []
  const response = await listKnowledgeFiles(settingsStore.profile.userId)
  const formsRoot = response.tree.find((node) => node.isDir && node.path === FORMS_ROOT_DIR)
  return (formsRoot?.children ?? [])
    .filter((node) => node.isDir)
    .map((node) => ({
      name: node.name,
      dir: node.path,
      metaPath: `${node.path}/form.json`,
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

/** Opens an existing table metadata file from its knowledge/forms folder. */
async function openForm(entry: SmartFormEntry): Promise<void> {
  if (!settingsStore.profile.userId) return
  try {
    const response = await readKnowledgeFile(settingsStore.profile.userId, entry.metaPath)
    form.value = normalizeForm(JSON.parse(response.content) as SmartLiteratureForm)
    activeFormDir.value = entry.dir
    selectedCell.value = null
  } catch (error) {
    workspaceStore.showToast(`打开表格失败 - ${errorMessage(error)}`)
  }
}

/** Opens a table selected from the real forms list. */
function openFormByDir(dir: string): void {
  const entry = formEntries.value.find((item) => item.dir === dir)
  if (entry) void openForm(entry)
}

/** Creates a user-named table folder and persists its initial metadata. */
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
  const existingDirs = new Set(formEntries.value.map((entry) => entry.dir))
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
    await writeKnowledgeFile(settingsStore.profile.userId, activeFormMetaFile.value, JSON.stringify(form.value, null, 2))
    await writeKnowledgeFile(settingsStore.profile.userId, activeFormCsvFile.value, exportCsv(form.value))
    await workspaceStore.loadKnowledgeTree()
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

function addRecord(): void {
  if (!form.value) return
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows: [...form.value.rows, createEmptyRow(form.value.columns)],
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

function insertBuiltinColumn(column: SmartColumn): void {
  if (!form.value) return
  if (form.value.columns.some((item) => item.id === column.id)) {
    workspaceStore.showToast('该内置列已存在')
    return
  }
  form.value = addColumn(form.value, { ...column })
  addColumnMenuOpen.value = false
}

function insertCustomColumn(): void {
  if (!form.value) return
  form.value = addColumn(form.value, createCustomColumn(customColumnTitle.value, customColumnType.value))
  customColumnTitle.value = ''
  addColumnMenuOpen.value = false
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
async function regenerateSmartCell(rowId: string, columnId: string): Promise<void> {
  selectedCell.value = { rowId, columnId }
  await generateSmartCellsForRows([rowId], [columnId], true)
}

async function generateSmartCellsForRows(rowIds: string[], columnIds?: string[], showSuccessToast = false): Promise<void> {
  if (!form.value) return
  const smartColumns = form.value.columns.filter((column) => {
    const isSmart = column.type === 'smart_text' || column.type === 'smart_tag'
    return isSmart && (!columnIds || columnIds.includes(column.id))
  })
  if (!smartColumns.length || !settingsStore.profile.userId) return
  const rowIdSet = new Set(rowIds)
  form.value = {
    ...form.value,
    updatedAt: new Date().toISOString(),
    rows: form.value.rows.map((row) => ({
      ...row,
      cells: Object.fromEntries(form.value.columns.map((column) => {
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
  <section class="smart-forms-view">
    <header class="forms-header">
      <div class="header-copy">
        <p class="forms-eyebrow">智能表格</p>
        <h1>{{ form?.title || '创建你的第一张表' }}</h1>
      </div>
      <div class="header-actions">
        <select
          v-if="formEntries.length > 1"
          class="form-select"
          :value="activeFormDir"
          title="切换表格"
          @change="openFormByDir(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="entry in formEntries" :key="entry.dir" :value="entry.dir">{{ entry.name }}</option>
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
      <button class="toolbar-btn strong" type="button" @click="addRecord">
        <IcIcon name="add" :size="16" />
        <span>添加记录</span>
      </button>
      <div class="column-menu-wrap">
        <button class="toolbar-btn" type="button" @click="addColumnMenuOpen = !addColumnMenuOpen">
          <IcIcon name="view-column" :size="16" />
          <span>字段配置</span>
        </button>
        <div v-if="addColumnMenuOpen" class="column-menu">
          <p>内置智能列</p>
          <div class="builtin-column-grid">
            <button
              v-for="column in BUILTIN_COLUMNS"
              :key="column.id"
              type="button"
              :disabled="form.columns.some((item) => item.id === column.id)"
              @click="insertBuiltinColumn(column)"
            >
              {{ column.title }}
            </button>
          </div>
          <hr />
          <div class="custom-column-editor">
            <input v-model="customColumnTitle" type="text" placeholder="列名" />
            <select v-model="customColumnType">
              <option v-for="type in customColumnTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
            </select>
          </div>
          <button class="menu-primary" type="button" @click="insertCustomColumn">插入自定义列</button>
        </div>
      </div>
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
      <span class="fill-chip">
        <IcIcon name="tune" :size="15" />
        <span>14 填色</span>
      </span>
      <span class="row-count">{{ rowCountLabel }}</span>
    </div>

    <div v-if="form" class="table-frame" :class="{ loading }">
      <table class="smart-table">
        <thead>
          <tr>
            <th class="row-actions-col"></th>
            <th
              v-for="(column, columnIndex) in form.columns"
              :key="column.id"
              :class="['tone-' + (column.tone || 'none'), { sticky: column.id === 'row_index' }]"
              :style="{ width: `${column.width}px`, minWidth: `${column.width}px` }"
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
            <td class="row-actions-col">
              <button type="button" title="上移" @click="moveRowById(row.id, -1)">
                <IcIcon name="arrow-up" :size="13" />
              </button>
              <button type="button" title="下移" @click="moveRowById(row.id, 1)">
                <IcIcon name="arrow-down" :size="13" />
              </button>
              <button type="button" title="删除行" @click="deleteRecord(row.id)">
                <IcIcon name="trash" :size="13" />
              </button>
            </td>
            <td
              v-for="column in form.columns"
              :key="column.id"
              :class="['cell', 'tone-' + (column.tone || 'none'), { sticky: column.id === 'row_index', selected: selectedCell?.rowId === row.id && selectedCell?.columnId === column.id }]"
              @click="selectedCell = { rowId: row.id, columnId: column.id }"
            >
              <span v-if="column.type === 'index'" class="row-index">{{ rowIndex + 1 }}</span>
              <div v-else-if="column.type === 'file'" class="file-cell">
                <button class="pdf-card" type="button" @click="openUpload(row.id)">
                  <IcIcon name="document" :size="20" />
                  <span>{{ row.cells[column.id]?.fileName || row.cells[column.id]?.value || '上传文献' }}</span>
                </button>
                <input
                  :ref="(el) => setUploadRef(row.id, el)"
                  class="hidden-input"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt,.md"
                  @change="uploadLiterature(row, $event)"
                />
              </div>
              <select
                v-else-if="column.type === 'tag' || column.type === 'smart_tag' || column.type === 'boolean'"
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
                @input="editCell(row, column, ($event.target as HTMLTextAreaElement).value)"
              ></textarea>
              <button
                v-if="column.type === 'smart_text' || column.type === 'smart_tag'"
                class="cell-generate-btn"
                type="button"
                title="重新生成该格"
                :disabled="row.cells[column.id]?.status === 'pending'"
                @click.stop="regenerateSmartCell(row.id, column.id)"
              >
                <IcIcon name="auto-awesome" :size="14" />
              </button>
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

    <footer v-if="form" class="forms-footer">
      <span>存储: {{ activeFormMetaFile }}</span>
      <span>CSV 镜像: {{ activeFormCsvFile }}</span>
      <span>更新: {{ updatedAtLabel }}</span>
    </footer>
  </section>
</template>

<style scoped>
.smart-forms-view {
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr) auto;
  min-height: 0;
  height: 100%;
  background: var(--color-canvas);
  color: var(--color-text);
}

.forms-header,
.forms-toolbar,
.view-tabs,
.forms-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.forms-header {
  justify-content: space-between;
  padding: 14px 18px 12px;
}

.header-copy {
  min-width: 0;
}

.forms-eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.forms-header h1 {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 650;
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
.view-tab,
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.primary-btn {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
  padding: 0 12px;
}

.ghost-btn,
.toolbar-btn {
  padding: 0 10px;
}

.toolbar-btn.strong {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 42%, var(--color-border));
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.view-tabs {
  padding: 0 16px;
  height: 42px;
  gap: 4px;
  overflow-x: auto;
}

.view-tab {
  height: 32px;
  border-color: transparent;
  background: transparent;
  color: var(--color-text-secondary);
}

.view-tab.active {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.add-tab {
  width: 32px;
}

.forms-toolbar {
  position: relative;
  padding: 9px 16px;
  flex-wrap: wrap;
}

.search-box {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 180px;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
}

.search-box input,
.filter-select,
.form-select,
.column-menu input,
.column-menu select {
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
  height: 30px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0 8px;
  background: var(--color-surface);
}

.form-select,
.new-form-input {
  height: 30px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0 8px;
  background: var(--color-surface);
  color: var(--color-text);
}

.form-empty-state {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 280px;
  padding: 24px;
  color: var(--color-text-muted);
  background: var(--color-surface);
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
  padding: 4px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  box-shadow: var(--shadow-md);
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
  background: var(--color-surface-raised);
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
  border-radius: var(--radius-md);
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
  background: var(--color-surface-raised);
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

.fill-chip,
.row-count {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 9px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-warning) 18%, transparent);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.row-count {
  margin-left: auto;
  background: transparent;
}

.column-menu-wrap {
  position: relative;
}

.column-menu {
  position: absolute;
  top: 34px;
  left: 0;
  z-index: 20;
  display: grid;
  gap: 8px;
  width: 340px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-window);
}

.column-menu p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.builtin-column-grid,
.custom-column-editor {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.column-menu button,
.column-menu input,
.column-menu select {
  width: 100%;
  min-height: 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  padding: 4px 8px;
}

.column-menu input {
  text-align: left;
}

.column-menu hr {
  width: 100%;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.column-menu .menu-primary {
  text-align: center;
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.table-frame {
  position: relative;
  min-height: 0;
  overflow: auto;
  background: var(--color-surface);
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
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  vertical-align: top;
}

th {
  position: sticky;
  top: 0;
  z-index: 4;
  height: 42px;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.column-head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  min-width: 0;
  padding: 8px 32px 8px 8px;
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

.column-actions button,
.row-actions-col button {
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
}

.row-actions-col {
  position: sticky;
  left: 0;
  z-index: 5;
  width: 78px;
  min-width: 78px;
  background: var(--color-surface-raised);
}

td.row-actions-col {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 112px;
  padding: 6px;
}

.cell {
  position: relative;
  height: 112px;
  background: var(--color-surface);
}

.cell.selected {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.sticky {
  position: sticky;
  left: 78px;
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
  width: 100%;
  height: 100%;
  min-height: 110px;
  resize: none;
  border: 0;
  outline: 0;
  padding: 11px;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  line-height: 1.35;
}

.cell:has(.cell-generate-btn) textarea,
.cell:has(.cell-generate-btn) select,
.cell:has(.cell-generate-btn) input {
  padding-right: 34px;
}

.cell select,
.cell input {
  min-height: 40px;
  height: 40px;
}

.cell-generate-btn {
  position: absolute;
  top: 7px;
  right: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-raised) 88%, transparent);
  color: var(--color-primary);
  opacity: 0;
  cursor: pointer;
  transition: opacity 120ms ease, background 120ms ease;
}

.cell:hover .cell-generate-btn,
.cell.selected .cell-generate-btn,
.cell-generate-btn:focus-visible {
  opacity: 1;
}

.cell-generate-btn:hover:not(:disabled) {
  background: var(--color-primary-softer);
}

.file-cell {
  padding: 10px;
}

.pdf-card {
  display: grid;
  grid-template-rows: auto 1fr;
  align-items: center;
  justify-items: center;
  gap: 8px;
  width: 100%;
  height: 92px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 10%, transparent), transparent);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow: hidden;
}

.pdf-card span {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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
  background: color-mix(in srgb, var(--color-primary) 7%, var(--color-surface));
}

.tone-green {
  background: color-mix(in srgb, var(--color-success) 10%, var(--color-surface));
}

.tone-amber {
  background: color-mix(in srgb, var(--color-warning) 12%, var(--color-surface));
}

.tone-rose {
  background: color-mix(in srgb, var(--color-accent) 8%, var(--color-surface));
}

.tone-violet {
  background: color-mix(in srgb, var(--color-primary) 10%, var(--color-surface));
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
  padding: 0 16px;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
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
