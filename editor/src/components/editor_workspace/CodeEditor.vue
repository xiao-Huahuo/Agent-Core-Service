<!--
  Code editor surface.

  Usage:
  Provides a lightweight textarea-based code editor for supported source files.
  Source files use the same highlight.js registry as CodePreview.vue while
  keeping the textarea as the editable input layer.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { useSubmenuIntent } from '@/components/editor_workspace/submenuIntent'
import WikiLinkSuggest from '@/components/editor_workspace/WikiLinkSuggest.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'

import { hljs, isHighlightableLanguage } from './codeHighlight'
import {
  findWikiLinkTrigger,
  wikiLinkSuggestions,
  type WikiLinkSuggestion,
  type WikiLinkTrigger,
} from './wikiLinks'

const model = defineModel<string>({ required: true })

const props = defineProps<{
  language: string
  readonly?: boolean
  /** Optional query highlighted by readonly consumers such as search preview. */
  highlightQuery?: string
  /** Saves a pasted clipboard image and returns the Markdown image token. */
  pasteImage?: (file: File) => Promise<string>
  /** Agent patch ranges rendered as non-interactive translucent gutter bars. */
  changeRanges?: Array<{ startLine: number; endLine: number; kind: 'added' | 'removed' }>
  /** Knowledge files offered after typing [[ or ![[ in Markdown. */
  wikiFiles?: KnowledgeFileNode[]
}>()

/** Scroll and caret data used by EditorPane to synchronize Markdown Split mode. */
interface EditorScrollPayload {
  ratio: number
  cursorOffset: number
  contentLength: number
}

const emit = defineEmits<{
  save: []
  scroll: [payload: EditorScrollPayload]
}>()

type MarkdownCommand =
  | 'save'
  | 'bold'
  | 'italic'
  | 'strike'
  | 'highlight'
  | 'inline-code'
  | 'code-fence'
  | 'inline-math'
  | 'comment'
  | 'ul'
  | 'ol'
  | 'quote'
  | 'paragraph'
  | 'heading-1'
  | 'heading-2'
  | 'heading-3'
  | 'heading-4'
  | 'heading-5'
  | 'heading-6'
  | 'table'
  | 'table-row-above'
  | 'table-row-below'
  | 'table-column-left'
  | 'table-column-right'
  | 'table-row-delete'
  | 'table-column-delete'
  | 'hr'
  | 'insert-code-block'
  | 'math-block'
  | 'wiki-link'
  | 'wiki-embed'
  | 'cut'
  | 'copy'
  | 'paste'
  | 'paste-plain'
  | 'select-all'
  | 'find-replace'
  | 'undo'
  | 'redo'

interface MarkdownMenuItem {
  command: MarkdownCommand
  label: string
  shortcut?: string
}

interface MarkdownTableContext {
  startLine: number
  endLine: number
  separatorLine: number
  currentLine: number
  currentColumn: number
  lines: string[]
  offsets: number[]
}

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const findInputRef = ref<HTMLInputElement | null>(null)
const highlightRef = ref<HTMLDivElement | null>(null)
const highlightContentRef = ref<HTMLDivElement | null>(null)
const contextMenuOpen = ref(false)
const undoStack = ref<string[]>([])
const redoStack = ref<string[]>([])
let ignoreUndoRedo = false
let pendingInputSnapshot: string | null = null
if (model.value) {
  undoStack.value = [model.value]
}
const contextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
const activeMenuGroup = ref('')
const markdownSubmenuRefs: Record<string, HTMLElement | null> = {}
const {
  openSubmenu: openMarkdownSubmenu,
  keepSubmenuOpen: keepMarkdownSubmenuOpen,
  scheduleSubmenuClose: scheduleMarkdownSubmenuClose,
  closeSubmenu: closeMarkdownSubmenu,
} = useSubmenuIntent(activeMenuGroup)
const findBarOpen = ref(false)
const findQuery = ref('')
const replaceQuery = ref('')
const currentMatchIndex = ref(0)
const wikiTrigger = ref<WikiLinkTrigger | null>(null)
const wikiActiveIndex = ref(0)
const wikiSuggestPosition = ref({ left: '12px', top: '42px' })
const wikiSuggestions = computed(() => (
  wikiTrigger.value ? wikiLinkSuggestions(props.wikiFiles ?? [], wikiTrigger.value.query) : []
))
const tableOverlay = ref<{
  visible: boolean
  showLeftEdge: boolean
  showTopEdge: boolean
  showRightEdge: boolean
  showBottomEdge: boolean
  left: number
  top: number
  width: number
  height: number
  rowTop: number
  rowHeight: number
  columnLeft: number
  columnWidth: number
  rowIndex: number
  columnIndex: number
}>({
  visible: false,
  showLeftEdge: false,
  showTopEdge: false,
  showRightEdge: false,
  showBottomEdge: false,
  left: 0,
  top: 0,
  width: 0,
  height: 0,
  rowTop: 0,
  rowHeight: 0,
  columnLeft: 0,
  columnWidth: 0,
  rowIndex: 0,
  columnIndex: 0,
})
const tableOverlayElement = ref<HTMLDivElement | null>(null)
const TABLE_EDGE_BUTTON_SIZE = 9
const TABLE_EDGE_HIT_ZONE = 14
let tableDrag: { type: 'row' | 'column'; source: number } | null = null
let programmaticScroll = false
/** Keeps Agent patch bars aligned with the textarea's independently scrolling text. */
const editorScrollTop = ref(0)
const isMarkdown = computed(() => ['md', 'markdown'].includes((props.language || '').toLowerCase()))
const isSyntaxHighlightedLanguage = computed(() => (
  isHighlightableLanguage(props.language || 'text')
))
const changeBarStyle = computed(() => props.changeRanges?.map((range) => ({
  top: `calc(var(--space-12) + ${(Math.max(1, range.startLine) - 1) * 1.6}em)`,
  height: `${Math.max(1, range.endLine - range.startLine + 1) * 1.6}em`,
  kind: range.kind,
})) ?? [])
/** Uses the find-bar query when open, otherwise the external preview query. */
const activeHighlightQuery = computed(() => (
  findBarOpen.value ? findQuery.value : (props.highlightQuery?.trim() ?? '')
))
const matches = computed(() => {
  if (!activeHighlightQuery.value) {
    return []
  }
  const result: Array<{ start: number; end: number }> = []
  const haystack = model.value.toLowerCase()
  const needle = activeHighlightQuery.value.toLowerCase()
  let cursor = 0
  while (cursor <= haystack.length) {
    const found = haystack.indexOf(needle, cursor)
    if (found < 0) {
      break
    }
    result.push({ start: found, end: found + activeHighlightQuery.value.length })
    cursor = found + Math.max(1, needle.length)
  }
  return result
})

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const highlightedHtml = computed(() => {
  const content = model.value
  if (isSyntaxHighlightedLanguage.value && !activeHighlightQuery.value) {
    return hljs.highlight(content, { language: props.language }).value
  }
  if (!activeHighlightQuery.value || !content) {
    return escapeHtml(content)
  }
  const ms = matches.value
  if (ms.length === 0) {
    return escapeHtml(content)
  }
  let result = ''
  let pos = 0
  for (let i = 0; i < ms.length; i++) {
    const m = ms[i]
    if (!m) {
      continue
    }
    if (m.start > pos) {
      result += escapeHtml(content.slice(pos, m.start))
    }
    const cls = findBarOpen.value && i === currentMatchIndex.value ? 'match-current' : 'match-highlight'
    result += `<span class="${cls}">${escapeHtml(content.slice(m.start, m.end))}</span>`
    pos = m.end
  }
  if (pos < content.length) {
    result += escapeHtml(content.slice(pos))
  }
  return result
})

const menuGroups: Array<{
  title: string
  items: MarkdownMenuItem[]
}> = [
  {
    title: '文本格式',
    items: [
      { command: 'bold', label: '加粗', shortcut: 'Ctrl+B' },
      { command: 'italic', label: '倾斜', shortcut: 'Ctrl+I' },
      { command: 'strike', label: '删除线', shortcut: 'Ctrl+D' },
      { command: 'highlight', label: '高亮' },
      { command: 'inline-code', label: '代码' },
      { command: 'code-fence', label: '多行代码' },
      { command: 'inline-math', label: '数学' },
      { command: 'comment', label: '注释' },
    ],
  },
  {
    title: '段落设置',
    items: [
      { command: 'ul', label: '无序列表' },
      { command: 'ol', label: '有序列表' },
      { command: 'heading-1', label: '1 级标题' },
      { command: 'heading-2', label: '2 级标题' },
      { command: 'heading-3', label: '3 级标题' },
      { command: 'heading-4', label: '4 级标题' },
      { command: 'heading-5', label: '5 级标题' },
      { command: 'heading-6', label: '6 级标题' },
      { command: 'paragraph', label: '正文' },
      { command: 'quote', label: '引用' },
    ],
  },
  {
    title: '插入',
    items: [
      { command: 'table', label: '表格' },
      { command: 'hr', label: '分割线' },
      { command: 'insert-code-block', label: '代码块' },
      { command: 'math-block', label: '数学块' },
      { command: 'wiki-link', label: '插入反向链接' },
      { command: 'wiki-embed', label: '插入嵌入链接' },
    ],
  },
  {
    title: '插入行',
    items: [
      { command: 'table-row-above', label: '上方插入' },
      { command: 'table-row-below', label: '下方插入' },
    ],
  },
  {
    title: '插入列',
    items: [
      { command: 'table-column-left', label: '左侧插入' },
      { command: 'table-column-right', label: '右侧插入' },
    ],
  },
  {
    title: '删除',
    items: [
      { command: 'table-row-delete', label: '删除整行' },
      { command: 'table-column-delete', label: '删除整列' },
    ],
  },
  {
    title: '编辑',
    items: [
      { command: 'save', label: '保存', shortcut: 'Ctrl+S' },
      { command: 'cut', label: '剪切', shortcut: 'Ctrl+X' },
      { command: 'copy', label: '复制', shortcut: 'Ctrl+C' },
      { command: 'paste', label: '粘贴', shortcut: 'Ctrl+V' },
      { command: 'paste-plain', label: '纯文本粘贴', shortcut: 'Ctrl+Shift+V' },
      { command: 'select-all', label: '全选', shortcut: 'Ctrl+A' },
      { command: 'find-replace', label: '查找替换', shortcut: 'Ctrl+F' },
      { command: 'undo', label: '撤销', shortcut: 'Ctrl+Z' },
      { command: 'redo', label: '反撤销', shortcut: 'Ctrl+Y' },
    ],
  },
]

function markdownGroupIcon(title: string): string {
  const icons: Record<string, string> = {
    '文本格式': 'text-fields',
    '段落设置': 'view-list',
    '插入': 'add',
    '插入行': 'table-chart',
    '插入列': 'view-column',
    '删除': 'trash',
    '编辑': 'edit',
  }
  return icons[title] ?? 'more-horiz'
}

function markdownCommandIcon(command: MarkdownCommand): string {
  const icons: Record<MarkdownCommand, string> = {
    save: 'save',
    bold: 'title',
    italic: 'edit-note',
    strike: 'remove',
    highlight: 'auto-awesome',
    'inline-code': 'code',
    'code-fence': 'code',
    'inline-math': 'table-chart',
    comment: 'add-comment',
    ul: 'checklist',
    ol: 'view-list',
    quote: 'forum',
    paragraph: 'text-fields',
    'heading-1': 'title',
    'heading-2': 'title',
    'heading-3': 'title',
    'heading-4': 'title',
    'heading-5': 'title',
    'heading-6': 'title',
    table: 'table-chart',
    'table-row-above': 'arrow-upward',
    'table-row-below': 'arrow-downward',
    'table-column-left': 'arrow-left',
    'table-column-right': 'arrow-right',
    'table-row-delete': 'trash',
    'table-column-delete': 'trash',
    hr: 'remove',
    'insert-code-block': 'code',
    'math-block': 'table-chart',
    'wiki-link': 'link',
    'wiki-embed': 'insert-drive-file',
    cut: 'cut',
    copy: 'copy',
    paste: 'paste',
    'paste-plain': 'paste',
    'select-all': 'multi-select',
    'find-replace': 'search',
    undo: 'replay',
    redo: 'refresh',
  }
  return icons[command]
}

watch(findQuery, () => {
  if (findBarOpen.value) {
    currentMatchIndex.value = matches.value.length > 0 ? 0 : -1
  }
})

function flushTypingSnapshot() {
  if (ignoreUndoRedo || pendingInputSnapshot === null) return
  undoStack.value.push(pendingInputSnapshot)
  if (undoStack.value.length > 100) undoStack.value.shift()
  redoStack.value = []
  pendingInputSnapshot = null
}

/** Returns the textarea caret location relative to the editor wrapper. */
function textareaCaretPosition(textarea: HTMLTextAreaElement) {
  const mirror = document.createElement('div')
  const style = window.getComputedStyle(textarea)
  const copiedProperties = [
    'boxSizing', 'width', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
    'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
    'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'letterSpacing', 'lineHeight',
    'textTransform', 'textIndent', 'tabSize', 'wordSpacing',
  ] as const
  for (const property of copiedProperties) {
    mirror.style[property] = style[property]
  }
  mirror.style.position = 'fixed'
  mirror.style.left = '-10000px'
  mirror.style.top = '0'
  mirror.style.visibility = 'hidden'
  mirror.style.whiteSpace = 'pre-wrap'
  mirror.style.overflowWrap = 'break-word'
  mirror.textContent = textarea.value.slice(0, textarea.selectionStart)
  const marker = document.createElement('span')
  marker.textContent = textarea.value.slice(textarea.selectionStart) || '.'
  mirror.appendChild(marker)
  document.body.appendChild(mirror)
  const lineHeight = Number.parseFloat(style.lineHeight) || Number.parseFloat(style.fontSize) * 1.6 || 22
  const position = {
    left: marker.offsetLeft - textarea.scrollLeft,
    top: marker.offsetTop - textarea.scrollTop + lineHeight,
  }
  mirror.remove()
  return position
}

/** Repositions and refreshes the wiki menu from the current Markdown caret. */
function updateWikiSuggestions() {
  const textarea = textareaRef.value
  if (!textarea || !isMarkdown.value || props.readonly || textarea.selectionStart !== textarea.selectionEnd) {
    wikiTrigger.value = null
    return
  }
  const trigger = findWikiLinkTrigger(textarea.value, textarea.selectionStart)
  wikiTrigger.value = trigger
  if (!trigger) return
  wikiActiveIndex.value = 0
  const wrapper = textarea.closest('.editor-wrapper') as HTMLElement | null
  const caret = textareaCaretPosition(textarea)
  const menuWidth = Math.min(420, Math.max(240, (wrapper?.clientWidth ?? 440) - 24))
  const left = Math.max(8, Math.min(textarea.offsetLeft + caret.left, (wrapper?.clientWidth ?? 440) - menuWidth - 8))
  const preferredTop = textarea.offsetTop + caret.top
  const top = preferredTop + 340 < (wrapper?.clientHeight ?? 700)
    ? preferredTop
    : Math.max(8, preferredTop - 340)
  wikiSuggestPosition.value = { left: `${left}px`, top: `${top}px` }
}

/** Flushes native typing history and updates the wiki-link completion state. */
function handleEditorInput() {
  flushTypingSnapshot()
  updateWikiSuggestions()
}

/** Replaces the incomplete token with the selected knowledge-file target. */
function selectWikiSuggestion(item: WikiLinkSuggestion) {
  const trigger = wikiTrigger.value
  const textarea = textareaRef.value
  if (!trigger || !textarea) return
  const token = `${trigger.embed ? '!' : ''}[[${item.target}]]`
  wikiTrigger.value = null
  replaceRange(trigger.start, textarea.selectionStart, token, trigger.start + token.length)
}

/** Inserts a wiki-link prefix from the context menu and opens file completion. */
function insertWikiLink(embed: boolean) {
  const selection = selectedRange()
  const prefix = embed ? '![[' : '[['
  if (selection.selected) {
    replaceRange(
      selection.start,
      selection.end,
      `${prefix}${selection.selected}]]`,
      selection.start + prefix.length + selection.selected.length + 2,
    )
    return
  }
  replaceRange(selection.start, selection.end, prefix, selection.start + prefix.length)
  void nextTick(updateWikiSuggestions)
}

function pushSnapshot() {
  undoStack.value.push(model.value)
  if (undoStack.value.length > 100) {
    undoStack.value.shift()
  }
  redoStack.value = []
}

function undo() {
  if (undoStack.value.length === 0) return
  const current = model.value
  const prev = undoStack.value.pop()!
  redoStack.value.push(current)
  ignoreUndoRedo = true
  model.value = prev
  ignoreUndoRedo = false
  void nextTick(() => {
    const ta = textareaRef.value
    if (ta) { ta.focus(); ta.setSelectionRange(prev.length, prev.length) }
  })
}

function redo() {
  if (redoStack.value.length === 0) return
  const current = model.value
  const next = redoStack.value.pop()!
  undoStack.value.push(current)
  ignoreUndoRedo = true
  model.value = next
  ignoreUndoRedo = false
  void nextTick(() => {
    const ta = textareaRef.value
    if (ta) { ta.focus(); ta.setSelectionRange(next.length, next.length) }
  })
}

function selectedRange() {
  const textarea = textareaRef.value
  if (!textarea) {
    return { start: 0, end: 0, selected: '' }
  }
  return {
    start: textarea.selectionStart,
    end: textarea.selectionEnd,
    selected: model.value.slice(textarea.selectionStart, textarea.selectionEnd),
  }
}

function replaceRange(start: number, end: number, text: string, selectionStart = start + text.length, selectionEnd = selectionStart) {
  pendingInputSnapshot = null
  pushSnapshot()
  model.value = `${model.value.slice(0, start)}${text}${model.value.slice(end)}`
  void nextTick(() => {
    const textarea = textareaRef.value
    if (!textarea) return
    textarea.focus()
    textarea.setSelectionRange(selectionStart, selectionEnd)
  })
}

function wrapSelection(prefix: string, suffix = prefix, placeholder = '文本', explicitRange?: { start: number; end: number; selected: string }) {
  const { start, end, selected } = explicitRange ?? selectedRange()
  const body = selected || placeholder
  replaceRange(start, end, `${prefix}${body}${suffix}`, start + prefix.length, start + prefix.length + body.length)
}

function lineBounds(start: number, end: number) {
  const content = model.value
  const lineStart = content.lastIndexOf('\n', Math.max(0, start - 1)) + 1
  let lineEnd = content.indexOf('\n', end)
  if (lineEnd < 0) lineEnd = content.length
  return { lineStart, lineEnd }
}

function lineStartOffsets(content: string): number[] {
  const offsets = [0]
  for (let index = 0; index < content.length; index += 1) {
    if (content[index] === '\n') {
      offsets.push(index + 1)
    }
  }
  return offsets
}

function lineIndexAtOffset(offsets: number[], offset: number): number {
  for (let index = offsets.length - 1; index >= 0; index -= 1) {
    const lineOffset = offsets[index]
    if (lineOffset !== undefined && offset >= lineOffset) {
      return index
    }
  }
  return 0
}

function isMarkdownTableRow(line: string): boolean {
  const trimmed = line.trim()
  return trimmed.includes('|') && trimmed.split('|').length >= 3
}

function isMarkdownTableSeparator(line: string): boolean {
  const cells = parseTableRow(line)
  if (cells.length < 2) {
    return false
  }
  return cells.every((cell) => /^:?-{3,}:?$/u.test(cell.trim()))
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim()
  const body = trimmed.replace(/^\|/u, '').replace(/\|$/u, '')
  return body.split('|').map((cell) => cell.trim())
}

function formatTableRow(cells: string[]): string {
  return `| ${cells.map((cell) => cell.trim() || ' ').join(' | ')} |`
}

function formatTableSeparator(columnCount: number): string {
  return `| ${Array.from({ length: Math.max(1, columnCount) }, () => '---').join(' | ')} |`
}

function normalizeTableRows(lines: string[]): string[] {
  const columnCount = Math.max(...lines.map((line) => parseTableRow(line).length), 1)
  return lines.map((line) => {
    if (isMarkdownTableSeparator(line)) {
      return formatTableSeparator(columnCount)
    }
    const cells = parseTableRow(line)
    while (cells.length < columnCount) {
      cells.push('')
    }
    return formatTableRow(cells.slice(0, columnCount))
  })
}

function columnIndexForLine(line: string, columnOffset: number): number {
  const pipePositions: number[] = []
  for (let index = 0; index < line.length; index += 1) {
    if (line[index] === '|') {
      pipePositions.push(index)
    }
  }
  if (pipePositions.length < 2) {
    return 0
  }
  for (let index = 0; index < pipePositions.length - 1; index += 1) {
    const start = pipePositions[index] ?? 0
    const end = pipePositions[index + 1] ?? line.length
    if (columnOffset <= end) {
      return Math.max(0, index)
    }
    if (columnOffset >= start && columnOffset <= end) {
      return Math.max(0, index)
    }
  }
  return Math.max(0, pipePositions.length - 2)
}

function findMarkdownTableContext(offset = selectedRange().start): MarkdownTableContext | null {
  const content = model.value
  const lines = content.split('\n')
  const offsets = lineStartOffsets(content)
  const currentLine = lineIndexAtOffset(offsets, offset)
  const currentText = lines[currentLine] ?? ''
  if (!isMarkdownTableRow(currentText)) {
    return null
  }
  let startLine = currentLine
  while (startLine > 0 && isMarkdownTableRow(lines[startLine - 1] ?? '')) {
    startLine -= 1
  }
  let endLine = currentLine
  while (endLine < lines.length - 1 && isMarkdownTableRow(lines[endLine + 1] ?? '')) {
    endLine += 1
  }
  const separatorLine = lines.findIndex((line, index) => (
    index >= startLine && index <= endLine && isMarkdownTableSeparator(line)
  ))
  if (separatorLine < startLine || separatorLine > endLine) {
    return null
  }
  const columnOffset = offset - (offsets[currentLine] ?? 0)
  return {
    startLine,
    endLine,
    separatorLine,
    currentLine,
    currentColumn: columnIndexForLine(currentText, columnOffset),
    lines: lines.slice(startLine, endLine + 1),
    offsets,
  }
}

function markdownTableContexts(offsets = lineStartOffsets(model.value)): MarkdownTableContext[] {
  const lines = model.value.split('\n')
  const contexts: MarkdownTableContext[] = []
  let lineIndex = 0
  while (lineIndex < lines.length) {
    if (!isMarkdownTableRow(lines[lineIndex] ?? '')) {
      lineIndex += 1
      continue
    }
    const startLine = lineIndex
    let endLine = lineIndex
    while (endLine < lines.length - 1 && isMarkdownTableRow(lines[endLine + 1] ?? '')) {
      endLine += 1
    }
    const separatorLine = lines.findIndex((line, index) => (
      index >= startLine && index <= endLine && isMarkdownTableSeparator(line)
    ))
    if (separatorLine >= startLine && separatorLine <= endLine) {
      contexts.push({
        startLine,
        endLine,
        separatorLine,
        currentLine: startLine,
        currentColumn: 0,
        lines: lines.slice(startLine, endLine + 1),
        offsets,
      })
    }
    lineIndex = endLine + 1
  }
  return contexts
}

function replaceTableLines(ctx: MarkdownTableContext, nextLines: string[], selectionLine = ctx.currentLine) {
  const startOffset = ctx.offsets[ctx.startLine] ?? 0
  const afterEndLineOffset = ctx.endLine + 1 < ctx.offsets.length
    ? (ctx.offsets[ctx.endLine + 1] ?? model.value.length)
    : model.value.length
  const normalized = normalizeTableRows(nextLines).join('\n')
  const keepsTrailingBreak = afterEndLineOffset < model.value.length && model.value[afterEndLineOffset - 1] === '\n'
  const nextText = keepsTrailingBreak ? `${normalized}\n` : normalized
  const targetLine = Math.max(ctx.startLine, Math.min(ctx.startLine + nextLines.length - 1, selectionLine))
  replaceRange(startOffset, afterEndLineOffset, nextText, ctx.offsets[targetLine] ?? startOffset, ctx.offsets[targetLine] ?? startOffset)
}

function insertMarkdownTableRow(position: 'above' | 'below') {
  const ctx = findMarkdownTableContext()
  if (!ctx) return
  const rows = normalizeTableRows(ctx.lines)
  const columnCount = parseTableRow(rows[0] ?? '').length || 2
  const emptyRow = formatTableRow(Array.from({ length: columnCount }, () => ''))
  const relativeLine = ctx.currentLine - ctx.startLine
  const separatorRelativeLine = ctx.separatorLine - ctx.startLine
  let insertAt = position === 'above' ? relativeLine : relativeLine + 1
  if (insertAt <= separatorRelativeLine) {
    insertAt = separatorRelativeLine + 1
  }
  rows.splice(insertAt, 0, emptyRow)
  replaceTableLines(ctx, rows, ctx.startLine + insertAt)
}

function insertMarkdownTableColumn(side: 'left' | 'right') {
  const ctx = findMarkdownTableContext()
  if (!ctx) return
  const rows = normalizeTableRows(ctx.lines)
  const insertAt = ctx.currentColumn + (side === 'right' ? 1 : 0)
  const nextRows = rows.map((line) => {
    const cells = parseTableRow(line)
    cells.splice(Math.max(0, Math.min(insertAt, cells.length)), 0, '')
    return isMarkdownTableSeparator(line) ? formatTableSeparator(cells.length) : formatTableRow(cells)
  })
  replaceTableLines(ctx, nextRows)
}

function deleteMarkdownTableRow() {
  const ctx = findMarkdownTableContext()
  if (!ctx || ctx.currentLine === ctx.separatorLine) return
  const rows = normalizeTableRows(ctx.lines)
  const relativeLine = ctx.currentLine - ctx.startLine
  if (rows.length <= 2) return
  rows.splice(relativeLine, 1)
  replaceTableLines(ctx, rows, Math.min(ctx.endLine - 1, ctx.currentLine))
}

function deleteMarkdownTableColumn() {
  const ctx = findMarkdownTableContext()
  if (!ctx) return
  const rows = normalizeTableRows(ctx.lines)
  const columnCount = parseTableRow(rows[0] ?? '').length
  if (columnCount <= 1) return
  const deleteAt = Math.max(0, Math.min(ctx.currentColumn, columnCount - 1))
  const nextRows = rows.map((line) => {
    const cells = parseTableRow(line)
    cells.splice(deleteAt, 1)
    return isMarkdownTableSeparator(line) ? formatTableSeparator(cells.length) : formatTableRow(cells)
  })
  replaceTableLines(ctx, nextRows)
}

function moveMarkdownTableRow(sourceLine: number, targetLine: number) {
  const ctx = findMarkdownTableContext(ctxOffsetForLine(sourceLine))
  if (!ctx || sourceLine === ctx.separatorLine || targetLine === ctx.separatorLine) return
  const rows = normalizeTableRows(ctx.lines)
  const sourceIndex = sourceLine - ctx.startLine
  const targetIndex = Math.max(0, Math.min(rows.length - 1, targetLine - ctx.startLine))
  const [row] = rows.splice(sourceIndex, 1)
  if (!row) return
  rows.splice(targetIndex, 0, row)
  replaceTableLines(ctx, rows, ctx.startLine + targetIndex)
}

function moveMarkdownTableColumn(sourceColumn: number, targetColumn: number) {
  const ctx = findMarkdownTableContext()
  if (!ctx || sourceColumn === targetColumn) return
  const rows = normalizeTableRows(ctx.lines)
  const nextRows = rows.map((line) => {
    const cells = parseTableRow(line)
    const sourceIndex = Math.max(0, Math.min(sourceColumn, cells.length - 1))
    const targetIndex = Math.max(0, Math.min(targetColumn, cells.length - 1))
    const [cell] = cells.splice(sourceIndex, 1)
    if (cell === undefined) return line
    cells.splice(targetIndex, 0, cell)
    return isMarkdownTableSeparator(line) ? formatTableSeparator(cells.length) : formatTableRow(cells)
  })
  replaceTableLines(ctx, nextRows)
}

function ctxOffsetForLine(lineIndex: number): number {
  return lineStartOffsets(model.value)[lineIndex] ?? 0
}

function transformSelectedLines(transform: (line: string, index: number) => string) {
  const { start, end } = selectedRange()
  const { lineStart, lineEnd } = lineBounds(start, end)
  const text = model.value.slice(lineStart, lineEnd)
  const transformed = text.split('\n').map(transform).join('\n')
  replaceRange(lineStart, lineEnd, transformed, lineStart, lineStart + transformed.length)
}

function stripBlockPrefix(line: string): string {
  return line
    .replace(/^\s{0,3}(#{1,6})\s+/, '')
    .replace(/^\s{0,3}>\s?/, '')
    .replace(/^\s*[-*+]\s+/, '')
    .replace(/^\s*\d+[.)]\s+/, '')
}

function applyHeading(level: number) {
  transformSelectedLines((line) => {
    const body = stripBlockPrefix(line)
    return body ? `${'#'.repeat(level)} ${body}` : '#'.repeat(level)
  })
}

function insertBlock(text: string, cursorOffset = text.length) {
  const { start, end } = selectedRange()
  const needsLeadingBreak = start > 0 && !model.value.slice(0, start).endsWith('\n')
  const needsTrailingBreak = end < model.value.length && !model.value.slice(end).startsWith('\n')
  const insertion = `${needsLeadingBreak ? '\n' : ''}${text}${needsTrailingBreak ? '\n' : ''}`
  const cursor = start + (needsLeadingBreak ? 1 : 0) + cursorOffset
  replaceRange(start, end, insertion, cursor, cursor)
}

async function insertPastedImageFile(file: File): Promise<boolean> {
  if (!props.pasteImage || !isMarkdown.value) {
    return false
  }
  const markdown = await props.pasteImage(file)
  if (!markdown) {
    return false
  }
  const { start, end } = selectedRange()
  replaceRange(start, end, markdown)
  return true
}

async function pasteFromClipboard() {
  if (props.pasteImage && isMarkdown.value) {
    try {
      const items = await navigator.clipboard?.read?.()
      const imageItem = items?.find((item) => item.types.some((type) => type.startsWith('image/')))
      const imageType = imageItem?.types.find((type) => type.startsWith('image/'))
      if (imageItem && imageType) {
        const blob = await imageItem.getType(imageType)
        if (await insertPastedImageFile(new File([blob], 'clipboard-image', { type: blob.type || imageType }))) {
          return
        }
      }
    } catch {
      // Non-image clipboard paths should keep the existing text paste behavior.
    }
  }
  try {
    const text = await navigator.clipboard?.readText()
    if (text !== undefined) {
      const { start, end } = selectedRange()
      replaceRange(start, end, text)
      return
    }
  } catch {
    // Fall through to browser command for Electron/system clipboard paths.
  }
  document.execCommand('paste')
}

function handleNativePaste(event: ClipboardEvent) {
  if (!props.pasteImage || !isMarkdown.value || props.readonly) {
    return
  }
  const items = Array.from(event.clipboardData?.items ?? [])
  const imageItem = items.find((item) => item.type.startsWith('image/'))
  const file = imageItem?.getAsFile()
  if (!file) {
    return
  }
  event.preventDefault()
  void insertPastedImageFile(file)
}

function openFindBar() {
  const { selected } = selectedRange()
  findBarOpen.value = true
  if (selected && !selected.includes('\n')) {
    findQuery.value = selected
  }
  void nextTick(() => findInputRef.value?.focus())
}

function closeFindBar() {
  findBarOpen.value = false
  currentMatchIndex.value = -1
  textareaRef.value?.focus()
}

function selectMatch(index: number) {
  if (matches.value.length === 0) {
    currentMatchIndex.value = -1
    return
  }
  const nextIndex = ((index % matches.value.length) + matches.value.length) % matches.value.length
  const match = matches.value[nextIndex]
  if (!match) {
    currentMatchIndex.value = -1
    return
  }
  currentMatchIndex.value = nextIndex
  void nextTick(() => {
    const textarea = textareaRef.value
    if (!textarea) return
    textarea.setSelectionRange(match.start, match.end)
    textarea.scrollTop = Math.max(0, (model.value.slice(0, match.start).split('\n').length - 3) * 20)
  })
}

function getScrollSnapshot(): EditorScrollPayload {
  const textarea = textareaRef.value
  if (!textarea) {
    return { ratio: 0, cursorOffset: 0, contentLength: model.value.length }
  }
  const maxScrollTop = Math.max(0, textarea.scrollHeight - textarea.clientHeight)
  return {
    ratio: maxScrollTop > 0 ? textarea.scrollTop / maxScrollTop : 0,
    cursorOffset: textarea.selectionStart ?? 0,
    contentLength: model.value.length,
  }
}

function handleEditorScroll() {
  editorScrollTop.value = textareaRef.value?.scrollTop ?? 0
  syncScroll()
  tableOverlay.value.visible = false
  if (programmaticScroll) {
    return
  }
  emit('scroll', getScrollSnapshot())
}

function syncScroll() {
  const ta = textareaRef.value
  const content = highlightContentRef.value
  if (ta && content) {
    // 用 transform 平移而非 scrollTop:div 的 scrollTop 会把 padding 一起滚走,
    // 而 textarea 滚动时 padding 固定,导致滚动后高亮层与 textarea 文本错位。
    // 只平移承载完整文本的内层,外层裁剪视口保持不动;否则滚动后整个视口层会被移走。
    content.style.transform = `translate3d(${-ta.scrollLeft}px, ${-ta.scrollTop}px, 0)`
  }
}

/** Scrolls the editable surface without emitting a synchronization feedback event. */
function scrollToRatio(ratio: number) {
  const textarea = textareaRef.value
  if (!textarea) return
  const maxScrollTop = Math.max(0, textarea.scrollHeight - textarea.clientHeight)
  programmaticScroll = true
  textarea.scrollTop = Math.max(0, Math.min(1, ratio)) * maxScrollTop
  editorScrollTop.value = textarea.scrollTop
  syncScroll()
  requestAnimationFrame(() => { programmaticScroll = false })
}

defineExpose({ getScrollSnapshot, scrollToRatio })

function editorLineHeight(textarea: HTMLTextAreaElement): number {
  const computedStyle = window.getComputedStyle(textarea)
  const parsed = Number.parseFloat(computedStyle.lineHeight)
  if (Number.isFinite(parsed)) {
    return parsed
  }
  return Number.parseFloat(computedStyle.fontSize || '13') * 1.6
}

function editorCharWidth(textarea: HTMLTextAreaElement): number {
  const computedStyle = window.getComputedStyle(textarea)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return 8
  ctx.font = `${computedStyle.fontSize} ${computedStyle.fontFamily}`
  return Math.max(6, ctx.measureText('| --- |').width / 7)
}

function tableContextFromPointer(event: MouseEvent): MarkdownTableContext | null {
  const textarea = textareaRef.value
  if (!textarea || !isMarkdown.value || props.readonly) {
    return null
  }
  const rect = textarea.getBoundingClientRect()
  const computedStyle = window.getComputedStyle(textarea)
  const paddingTop = Number.parseFloat(computedStyle.paddingTop || '0')
  const paddingLeft = Number.parseFloat(computedStyle.paddingLeft || '0')
  const lineHeight = editorLineHeight(textarea)
  const charWidth = editorCharWidth(textarea)
  const lineIndex = Math.max(0, Math.floor((event.clientY - rect.top - paddingTop + textarea.scrollTop) / lineHeight))
  const columnOffset = Math.max(0, Math.floor((event.clientX - rect.left - paddingLeft + textarea.scrollLeft) / charWidth))
  const offsets = lineStartOffsets(model.value)
  const directContext = findMarkdownTableContext((offsets[lineIndex] ?? 0) + columnOffset)
  if (directContext) {
    return directContext
  }
  const tableContexts = markdownTableContexts(offsets)
  const edgeContext = tableContexts.find((ctx) => {
    const maxLineLength = Math.max(...ctx.lines.map((line) => line.length), 8)
    const left = rect.left + paddingLeft - textarea.scrollLeft
    const top = rect.top + paddingTop + ctx.startLine * lineHeight - textarea.scrollTop
    const right = left + Math.max(120, maxLineLength * charWidth)
    const bottom = top + (ctx.endLine - ctx.startLine + 1) * lineHeight
    return event.clientX >= left - TABLE_EDGE_BUTTON_SIZE
      && event.clientX <= right + TABLE_EDGE_BUTTON_SIZE
      && event.clientY >= top - TABLE_EDGE_BUTTON_SIZE
      && event.clientY <= bottom + TABLE_EDGE_BUTTON_SIZE
  })
  if (!edgeContext) {
    return null
  }
  const currentLine = Math.max(edgeContext.startLine, Math.min(edgeContext.endLine, lineIndex))
  const currentText = model.value.split('\n')[currentLine] ?? ''
  return {
    ...edgeContext,
    currentLine,
    currentColumn: columnIndexForLine(currentText, columnOffset),
  }
}

function updateTableOverlay(event: MouseEvent) {
  const textarea = textareaRef.value
  if (!textarea || tableDrag) {
    return
  }
  const eventTarget = event.target instanceof Element ? event.target : null
  if (eventTarget && tableOverlayElement.value?.contains(eventTarget)) {
    return
  }
  const ctx = tableContextFromPointer(event)
  if (!ctx) {
    tableOverlay.value.visible = false
    return
  }
  const rect = textarea.getBoundingClientRect()
  const computedStyle = window.getComputedStyle(textarea)
  const paddingTop = Number.parseFloat(computedStyle.paddingTop || '0')
  const paddingLeft = Number.parseFloat(computedStyle.paddingLeft || '0')
  const lineHeight = editorLineHeight(textarea)
  const charWidth = editorCharWidth(textarea)
  const maxLineLength = Math.max(...ctx.lines.map((line) => line.length), 8)
  const tableLeft = paddingLeft - textarea.scrollLeft
  const tableTop = paddingTop + ctx.startLine * lineHeight - textarea.scrollTop
  const tableWidth = Math.max(120, maxLineLength * charWidth)
  const tableHeight = (ctx.endLine - ctx.startLine + 1) * lineHeight
  const pointerX = event.clientX - rect.left
  const pointerY = event.clientY - rect.top
  const withinHorizontalEdgeBand = pointerX >= tableLeft - TABLE_EDGE_BUTTON_SIZE
    && pointerX <= tableLeft + tableWidth + TABLE_EDGE_BUTTON_SIZE
  const withinVerticalEdgeBand = pointerY >= tableTop - TABLE_EDGE_BUTTON_SIZE
    && pointerY <= tableTop + tableHeight + TABLE_EDGE_BUTTON_SIZE
  const showLeftEdge = withinVerticalEdgeBand
    && pointerX >= tableLeft - TABLE_EDGE_BUTTON_SIZE
    && pointerX <= tableLeft + TABLE_EDGE_HIT_ZONE
  const showTopEdge = withinHorizontalEdgeBand
    && pointerY >= tableTop - TABLE_EDGE_BUTTON_SIZE
    && pointerY <= tableTop + TABLE_EDGE_HIT_ZONE
  const showRightEdge = withinVerticalEdgeBand
    && pointerX >= tableLeft + tableWidth - TABLE_EDGE_HIT_ZONE
    && pointerX <= tableLeft + tableWidth + TABLE_EDGE_BUTTON_SIZE
  const showBottomEdge = withinHorizontalEdgeBand
    && pointerY >= tableTop + tableHeight - TABLE_EDGE_HIT_ZONE
    && pointerY <= tableTop + tableHeight + TABLE_EDGE_BUTTON_SIZE
  if (!showLeftEdge && !showTopEdge && !showRightEdge && !showBottomEdge) {
    tableOverlay.value.visible = false
    return
  }
  const currentLine = model.value.split('\n')[ctx.currentLine] ?? ''
  const pipes: number[] = []
  for (let index = 0; index < currentLine.length; index += 1) {
    if (currentLine[index] === '|') pipes.push(index)
  }
  const columnStart = pipes[ctx.currentColumn] ?? 0
  const columnEnd = pipes[ctx.currentColumn + 1] ?? (columnStart + 8)
  tableOverlay.value = {
    visible: true,
    showLeftEdge,
    showTopEdge,
    showRightEdge,
    showBottomEdge,
    left: tableLeft,
    top: tableTop,
    width: tableWidth,
    height: tableHeight,
    rowTop: paddingTop + ctx.currentLine * lineHeight - textarea.scrollTop,
    rowHeight: lineHeight,
    columnLeft: paddingLeft + columnStart * charWidth - textarea.scrollLeft,
    columnWidth: Math.max(24, (columnEnd - columnStart) * charWidth),
    rowIndex: ctx.currentLine,
    columnIndex: ctx.currentColumn,
  }
}

function offsetForTableCell(lineIndex: number, columnIndex: number): number {
  const lines = model.value.split('\n')
  const line = lines[lineIndex] ?? ''
  const offsets = lineStartOffsets(model.value)
  const pipes: number[] = []
  for (let index = 0; index < line.length; index += 1) {
    if (line[index] === '|') pipes.push(index)
  }
  return (offsets[lineIndex] ?? 0) + (pipes[columnIndex] ?? 0) + 1
}

function focusTablePosition(lineIndex: number, columnIndex: number) {
  const offset = offsetForTableCell(lineIndex, columnIndex)
  textareaRef.value?.focus()
  textareaRef.value?.setSelectionRange(offset, offset)
}

function addOverlayTableRow() {
  focusTablePosition(tableOverlay.value.rowIndex, tableOverlay.value.columnIndex)
  insertMarkdownTableRow('below')
}

function addOverlayTableColumn() {
  focusTablePosition(tableOverlay.value.rowIndex, tableOverlay.value.columnIndex)
  insertMarkdownTableColumn('right')
}

function beginTableDrag(type: 'row' | 'column', event: PointerEvent) {
  if (!tableOverlay.value.visible) return
  event.preventDefault()
  tableDrag = { type, source: type === 'row' ? tableOverlay.value.rowIndex : tableOverlay.value.columnIndex }
  document.addEventListener('pointerup', finishTableDrag)
}

function finishTableDrag(event: PointerEvent) {
  document.removeEventListener('pointerup', finishTableDrag)
  const drag = tableDrag
  tableDrag = null
  if (!drag) return
  const ctx = tableContextFromPointer(event)
  if (!ctx) return
  if (drag.type === 'row') {
    moveMarkdownTableRow(drag.source, ctx.currentLine)
  } else {
    focusTablePosition(ctx.currentLine, ctx.currentColumn)
    moveMarkdownTableColumn(drag.source, ctx.currentColumn)
  }
}

function findNext() {
  selectMatch(currentMatchIndex.value + 1)
}

function findPrevious() {
  selectMatch(currentMatchIndex.value - 1)
}

function replaceCurrent() {
  if (currentMatchIndex.value < 0 || currentMatchIndex.value >= matches.value.length) {
    return
  }
  const match = matches.value[currentMatchIndex.value]
  if (!match) {
    return
  }
  replaceRange(match.start, match.end, replaceQuery.value)
  void nextTick(() => selectMatch(currentMatchIndex.value))
}

function replaceAll() {
  if (!findQuery.value) {
    return
  }
  let nextValue = model.value
  for (const match of [...matches.value].reverse()) {
    nextValue = `${nextValue.slice(0, match.start)}${replaceQuery.value}${nextValue.slice(match.end)}`
  }
  pushSnapshot()
  pendingInputSnapshot = null
  model.value = nextValue
  currentMatchIndex.value = -1
  void nextTick(() => textareaRef.value?.focus())
}

async function copySelection(cut = false) {
  const { selected, start, end } = selectedRange()
  if (!selected) return
  try {
    await navigator.clipboard?.writeText(selected)
  } catch {
    document.execCommand(cut ? 'cut' : 'copy')
    return
  }
  if (cut) {
    replaceRange(start, end, '', start, start)
  }
}

async function runCommand(command: MarkdownCommand) {
  closeContextMenu()
  if (props.readonly && command !== 'copy' && command !== 'select-all') {
    return
  }
  switch (command) {
    case 'save': emit('save'); break
    case 'bold': wrapSelection('**'); break
    case 'italic': wrapSelection('*'); break
    case 'strike': wrapSelection('~~'); break
    case 'highlight': wrapSelection('=='); break
    case 'inline-code': wrapSelection('`', '`', 'code'); break
    case 'code-fence': wrapSelection('```\n', '\n```', 'code'); break
    case 'inline-math': wrapSelection('$', '$', 'x = y'); break
    case 'comment': wrapSelection('<!-- ', ' -->'); break
    case 'ul': transformSelectedLines((line) => `- ${stripBlockPrefix(line)}`); break
    case 'ol': transformSelectedLines((line, index) => `${index + 1}. ${stripBlockPrefix(line)}`); break
    case 'quote': transformSelectedLines((line) => `> ${line.replace(/^\s{0,3}>\s?/, '')}`); break
    case 'paragraph': transformSelectedLines((line) => stripBlockPrefix(line)); break
    case 'heading-1': applyHeading(1); break
    case 'heading-2': applyHeading(2); break
    case 'heading-3': applyHeading(3); break
    case 'heading-4': applyHeading(4); break
    case 'heading-5': applyHeading(5); break
    case 'heading-6': applyHeading(6); break
    case 'table': insertBlock('| 列 1 | 列 2 |\n| --- | --- |\n| 内容 | 内容 |'); break
    case 'table-row-above': insertMarkdownTableRow('above'); break
    case 'table-row-below': insertMarkdownTableRow('below'); break
    case 'table-column-left': insertMarkdownTableColumn('left'); break
    case 'table-column-right': insertMarkdownTableColumn('right'); break
    case 'table-row-delete': deleteMarkdownTableRow(); break
    case 'table-column-delete': deleteMarkdownTableColumn(); break
    case 'hr': insertBlock('---'); break
    case 'insert-code-block': insertBlock('```\n\n```', 4); break
    case 'math-block': insertBlock('$$\n\n$$', 3); break
    case 'wiki-link': insertWikiLink(false); break
    case 'wiki-embed': insertWikiLink(true); break
    case 'cut': await copySelection(true); break
    case 'copy': await copySelection(false); break
    case 'paste':
    case 'paste-plain': await pasteFromClipboard(); break
    case 'find-replace': openFindBar(); break
    case 'undo': undo(); break
    case 'redo': redo(); break
    case 'select-all':
      textareaRef.value?.focus()
      textareaRef.value?.select()
      break
  }
}

function handleEditorKeydown(event: KeyboardEvent) {
  // Capture pre-change value for native typing undo (non-modifier, content-changing keys)
  if (!props.readonly && !event.ctrlKey && !event.metaKey && !event.altKey &&
      (event.key.length === 1 || ['Backspace', 'Delete', 'Enter', 'Tab'].includes(event.key))) {
    pendingInputSnapshot = model.value
  }
  const isModifier = event.ctrlKey || event.metaKey
  const key = event.key.toLowerCase()
  if (isModifier && !event.altKey && key === 's') {
    event.preventDefault()
    handleSaveShortcut()
    return
  }
  if (wikiTrigger.value) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      const count = wikiSuggestions.value.length
      if (count > 0) wikiActiveIndex.value = (wikiActiveIndex.value + direction + count) % count
      return
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      const item = wikiSuggestions.value[wikiActiveIndex.value]
      if (item) {
        event.preventDefault()
        selectWikiSuggestion(item)
        return
      }
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      wikiTrigger.value = null
      return
    }
  }
  if (props.readonly) {
    if (isModifier && !event.altKey && key === 'f') {
      event.preventDefault()
      openFindBar()
    }
    return
  }
  const sel = selectedRange()
  if (!isModifier && !event.altKey) {
    const wrappers: Record<string, [string, string]> = {
      '*': ['*', '*'],
      '`': ['`', '`'],
      '$': ['$', '$'],
      '=': ['==', '=='],
      '~': ['~~', '~~'],
    }
    const pair = wrappers[event.key]
    if (pair && sel.selected) {
      event.preventDefault()
      wrapSelection(pair[0], pair[1], undefined, sel)
      return
    }
  }
  if (!isModifier || event.altKey) {
    return
  }
  if (event.shiftKey && key === 'v') {
    event.preventDefault()
    void pasteFromClipboard()
    return
  }
  if (key === 'f') {
    event.preventDefault()
    openFindBar()
    return
  }
  if (key === 'z' && !event.shiftKey) {
    event.preventDefault()
    undo()
    return
  }
  if (key === 'y' || (key === 'z' && event.shiftKey)) {
    event.preventDefault()
    redo()
    return
  }
  if (key === 'b') {
    event.preventDefault()
    wrapSelection('**', '**', undefined, sel)
    return
  }
  if (key === 'i') {
    event.preventDefault()
    wrapSelection('*', '*', undefined, sel)
    return
  }
  if (key === 'd') {
    event.preventDefault()
    wrapSelection('~~', '~~', undefined, sel)
  }
}

/** Emits save only for editable instances while consuming the browser shortcut. */
function handleSaveShortcut() {
  if (!props.readonly) {
    emit('save')
  }
}

function openContextMenu(event: MouseEvent) {
  if (!isMarkdown.value || props.readonly) {
    return
  }
  event.preventDefault()
  contextMenuOpen.value = true
  activeMenuGroup.value = menuGroups[0]?.title ?? ''
  const width = 320
  const height = 180
  const left = Math.min(event.clientX, window.innerWidth - width - 8)
  const top = Math.min(event.clientY, window.innerHeight - height - 8)
  contextMenuStyle.value = {
    left: `${Math.max(8, left)}px`,
    top: `${Math.max(8, top)}px`,
  }
  document.addEventListener('click', closeContextMenu, { once: true })
}

function closeContextMenu() {
  contextMenuOpen.value = false
  closeMarkdownSubmenu()
  activeMenuGroup.value = ''
}

function setMarkdownSubmenuRef(key: string, element: unknown) {
  markdownSubmenuRefs[key] = element instanceof HTMLElement ? element : null
}

function handleMarkdownSubmenuLeave(key: string, event: MouseEvent) {
  const parent = event.currentTarget
  if (parent instanceof HTMLElement) {
    scheduleMarkdownSubmenuClose(key, event, parent, markdownSubmenuRefs[key] ?? null)
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', closeContextMenu)
})
</script>

<template>
  <section class="code-editor">
    <div class="code-editor-header">
      <span>{{ language || 'text' }}</span>
    </div>
    <div v-if="findBarOpen" class="find-replace-bar">
      <div class="find-field-wrapper">
        <div class="find-field-row">
          <input
            ref="findInputRef"
            v-model="findQuery"
            placeholder="查找"
            class="find-input"
            @keydown.enter.exact.prevent="findNext"
            @keydown.shift.enter.prevent="findPrevious"
            @keydown.esc.prevent="closeFindBar"
          />
          <span class="match-count">{{ matches.length ? `${(currentMatchIndex < 0 ? 0 : currentMatchIndex) + 1}/${matches.length}` : '0/0' }}</span>
          <button type="button" class="nav-arrow" @click="findPrevious" title="上一个">↑</button>
          <button type="button" class="nav-arrow" @click="findNext" title="下一个">↓</button>
        </div>
        <input
          v-model="replaceQuery"
          placeholder="替换为"
          class="replace-input"
          @keydown.enter.prevent="replaceCurrent"
          @keydown.esc.prevent="closeFindBar"
        />
      </div>
      <div class="find-replace-actions">
        <button type="button" class="action-btn" @click="replaceCurrent">替换</button>
        <button type="button" class="action-btn" @click="replaceAll">全部替换</button>
        <button type="button" class="action-btn close-btn" @click="closeFindBar">关闭</button>
      </div>
    </div>
    <div
      class="editor-wrapper"
      @mousemove="updateTableOverlay"
      @mouseleave="tableOverlay.visible = false"
    >
      <div class="agent-change-gutter" :style="{ transform: `translateY(-${editorScrollTop}px)` }" aria-hidden="true">
        <span
          v-for="(bar, index) in changeBarStyle"
          :key="`${bar.kind}-${index}`"
          class="agent-change-bar"
          :class="bar.kind"
          :style="{ top: bar.top, height: bar.height }"
        ></span>
      </div>
      <div
        v-if="isSyntaxHighlightedLanguage || findBarOpen || Boolean(highlightQuery)"
        ref="highlightRef"
        class="highlight-layer"
        :class="{
          'syntax-highlight-layer': isSyntaxHighlightedLanguage,
          'markdown-highlight-layer': isMarkdown,
        }"
      >
        <div
          ref="highlightContentRef"
          class="highlight-content"
          v-html="highlightedHtml"
        ></div>
      </div>
      <textarea
        ref="textareaRef"
        v-model="model"
        class="code-editor-input"
        :class="{ readonly, 'syntax-highlighted': isSyntaxHighlightedLanguage }"
        spellcheck="false"
        :readonly="readonly"
        @keydown="handleEditorKeydown"
        @click="updateWikiSuggestions"
        @input="handleEditorInput"
        @paste="handleNativePaste"
        @scroll="handleEditorScroll"
        @contextmenu="openContextMenu"
      ></textarea>
      <WikiLinkSuggest
        v-if="wikiTrigger"
        :items="wikiSuggestions"
        :active-index="wikiActiveIndex"
        :position="wikiSuggestPosition"
        @activate="wikiActiveIndex = $event"
        @select="selectWikiSuggestion"
      />
      <div
        v-if="tableOverlay.visible"
        ref="tableOverlayElement"
        class="markdown-table-overlay"
        :style="{
          left: `${tableOverlay.left}px`,
          top: `${tableOverlay.top}px`,
          width: `${tableOverlay.width}px`,
          height: `${tableOverlay.height}px`,
        }"
      >
        <button
          v-if="tableOverlay.showLeftEdge"
          class="table-row-drag-handle"
          type="button"
          title="拖动表格行"
          :style="{ top: `${tableOverlay.rowTop - tableOverlay.top}px`, height: `${tableOverlay.rowHeight}px` }"
          @pointerdown="beginTableDrag('row', $event)"
        >
          <IcIcon name="unfold" :size="10" />
        </button>
        <button
          v-if="tableOverlay.showTopEdge"
          class="table-column-drag-handle"
          type="button"
          title="拖动表格列"
          :style="{ left: `${tableOverlay.columnLeft - tableOverlay.left}px`, width: `${tableOverlay.columnWidth}px` }"
          @pointerdown="beginTableDrag('column', $event)"
        >
          <IcIcon name="unfold" :size="10" />
        </button>
        <button
          v-if="tableOverlay.showBottomEdge"
          class="table-add-row-button"
          type="button"
          title="添加空行"
          @click="addOverlayTableRow"
        >
          <IcIcon name="add" :size="10" />
        </button>
        <button
          v-if="tableOverlay.showRightEdge"
          class="table-add-column-button"
          type="button"
          title="添加空列"
          @click="addOverlayTableColumn"
        >
          <IcIcon name="add" :size="10" />
        </button>
      </div>
    </div>
    <div
      v-if="contextMenuOpen"
      class="markdown-context-menu ui-floating-menu-surface"
      :style="contextMenuStyle"
      @click.stop
      @contextmenu.prevent
    >
      <div class="markdown-context-primary">
        <div
          v-for="group in menuGroups"
          :key="group.title"
          class="markdown-context-group"
          @mouseenter="openMarkdownSubmenu(group.title)"
          @mouseleave="handleMarkdownSubmenuLeave(group.title, $event)"
        >
          <button
            class="markdown-context-parent"
            :class="{ active: activeMenuGroup === group.title }"
            type="button"
            @click.stop="activeMenuGroup = activeMenuGroup === group.title ? '' : group.title"
          >
            <IcIcon :name="markdownGroupIcon(group.title)" :size="15" />
            <span>{{ group.title }}</span>
            <span aria-hidden="true">›</span>
          </button>
          <div
            v-if="activeMenuGroup === group.title"
            :ref="(element) => setMarkdownSubmenuRef(group.title, element)"
            class="markdown-context-submenu ui-floating-submenu-surface"
            @mouseenter="keepMarkdownSubmenuOpen"
            @mouseleave="handleMarkdownSubmenuLeave(group.title, $event)"
          >
            <button
              v-for="item in group.items"
              :key="item.command"
              type="button"
              @click="runCommand(item.command)"
            >
              <IcIcon :name="markdownCommandIcon(item.command)" :size="15" />
              <span>{{ item.label }}</span>
              <kbd v-if="item.shortcut">{{ item.shortcut }}</kbd>
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.code-editor {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: var(--color-canvas);
}

.code-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  height: 28px;
  padding: 0 var(--space-10);
  border-bottom: 0;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.find-replace-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8);
  border-bottom: 0;
  background: var(--color-canvas-soft);
}

.find-field-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.find-field-row {
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

.find-replace-bar input {
  flex: 1;
  min-width: 0;
  height: 24px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  outline: 0;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
}

.match-count {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  min-width: 32px;
  text-align: center;
}

.nav-arrow {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: calc(10px * var(--font-scale));
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.nav-arrow:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.find-replace-actions {
  display: flex;
  gap: var(--space-6);
}

.action-btn {
  height: 24px;
  padding: 0 var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  cursor: pointer;
  white-space: nowrap;
}

.action-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.close-btn {
  margin-left: auto;
}

.editor-wrapper {
  flex: 1;
  min-width: 0;
  min-height: 0;
  position: relative;
  overflow: hidden;
}

.agent-change-gutter {
  position: absolute;
  inset: 0 auto 0 0;
  z-index: 2;
  width: 4px;
  pointer-events: none;
}

.agent-change-bar {
  position: absolute;
  width: 2px;
  border-radius: 0 2px 2px 0;
  opacity: 0.78;
}

.agent-change-bar.added { left: 0; background: color-mix(in srgb, var(--color-primary) 76%, transparent); }
.agent-change-bar.removed { left: 2px; background: color-mix(in srgb, var(--color-danger) 76%, transparent); }

.highlight-layer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  color: transparent;
}

.highlight-content {
  min-width: 100%;
  min-height: 100%;
  padding: var(--space-12);
  font-family: var(--font-text);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
  tab-size: 2;
  white-space: pre;
  color: inherit;
  word-wrap: normal;
  will-change: transform;
}

.highlight-layer.syntax-highlight-layer {
  color: var(--color-text);
}

.highlight-layer :deep(.match-highlight) {
  background: rgba(255, 255, 0, 0.35);
  border-radius: 2px;
}

.highlight-layer :deep(.match-current) {
  background: color-mix(in srgb, var(--color-primary) 40%, transparent);
  border-radius: 2px;
  outline: 1px solid var(--color-primary);
}

/* markdown 编辑区:只着色,不改字重/斜体/字体,保证与 textarea 透明层逐像素对齐 */
.markdown-highlight-layer :deep(.hljs-section),
.markdown-highlight-layer :deep(.hljs-bullet),
.markdown-highlight-layer :deep(.hljs-link),
.markdown-highlight-layer :deep(.hljs-string),
.markdown-highlight-layer :deep(.hljs-strong) {
  color: var(--color-primary);
  font-weight: normal;
  font-style: normal;
}

.markdown-highlight-layer :deep(.hljs-emphasis) {
  color: var(--color-text-secondary);
  font-weight: normal;
  font-style: normal;
}

.markdown-highlight-layer :deep(.hljs-quote) {
  color: var(--color-text-muted);
  font-weight: normal;
  font-style: normal;
}

.markdown-highlight-layer :deep(.hljs-code) {
  color: var(--color-text-secondary);
  background: var(--color-code-bg);
  border-radius: 3px;
}

.code-editor-input {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  padding: var(--space-12);
  resize: none;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-text);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
  tab-size: 2;
  white-space: pre;
}

.code-editor-input.readonly {
  cursor: default;
  color: var(--color-text-secondary);
}

.code-editor-input.syntax-highlighted {
  color: transparent;
  caret-color: var(--color-text);
}

.code-editor-input.syntax-highlighted::selection {
  background: color-mix(in srgb, var(--color-primary) 28%, transparent);
  color: transparent;
}

.code-editor-input.syntax-highlighted::-moz-selection {
  background: color-mix(in srgb, var(--color-primary) 28%, transparent);
  color: transparent;
}

.markdown-table-overlay {
  position: absolute;
  z-index: 2;
  pointer-events: none;
}

.markdown-table-overlay button {
  position: absolute;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface-raised);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-border) 34%, transparent);
  color: var(--color-text-tertiary);
  pointer-events: auto;
  cursor: pointer;
}

.markdown-table-overlay button:hover {
  border-color: color-mix(in srgb, var(--color-text-tertiary) 45%, var(--color-border));
  background: var(--color-surface);
  color: var(--color-text-secondary);
}

.markdown-table-overlay button :deep(svg) {
  display: block;
  opacity: 0.72;
}

.table-row-drag-handle {
  left: -9px;
  width: 9px;
  cursor: grab;
}

.table-column-drag-handle {
  top: -9px;
  height: 9px;
  cursor: grab;
}

.table-column-drag-handle :deep(svg) {
  transform: rotate(90deg);
}

.table-row-drag-handle:active,
.table-column-drag-handle:active {
  cursor: grabbing;
}

.table-add-row-button {
  left: 0;
  right: 0;
  bottom: -9px;
  height: 9px;
}

.table-add-column-button {
  top: 0;
  right: -9px;
  bottom: 0;
  width: 9px;
}

.markdown-context-menu {
  position: fixed;
  z-index: 1200;
  width: 178px;
  padding: var(--space-6);
  font-family: var(--font-ui);
}

.markdown-context-primary {
  display: grid;
  gap: 2px;
}

.markdown-context-group {
  position: relative;
}

.markdown-context-parent {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  width: 100%;
}

.markdown-context-submenu {
  position: absolute;
  top: -6px;
  left: calc(100% + 8px);
  display: grid;
  min-width: 248px;
  max-height: min(360px, calc(100vh - 24px));
  overflow: auto;
  padding: var(--space-6);
}

.markdown-context-group button,
.markdown-context-submenu button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  column-gap: var(--space-10);
  height: 26px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  text-align: left;
}

.markdown-context-parent span,
.markdown-context-submenu button span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.markdown-context-submenu kbd {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  white-space: nowrap;
}

.markdown-context-group button:hover,
.markdown-context-parent.active,
.markdown-context-submenu button:hover {
  background: var(--color-canvas-soft);
  color: var(--color-primary);
}

@media (max-width: 820px) {
  .find-replace-actions {
    flex-wrap: wrap;
  }
}
</style>
