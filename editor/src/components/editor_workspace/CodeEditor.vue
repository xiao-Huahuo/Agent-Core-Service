<!--
  Code editor surface.

  Usage:
  Provides a lightweight textarea-based code editor for supported source files.
  Syntax highlighting is handled by CodePreview.vue in Preview/Split mode.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const model = defineModel<string>({ required: true })

const props = defineProps<{
  language: string
  readonly?: boolean
}>()

const emit = defineEmits<{
  save: []
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
  | 'hr'
  | 'insert-code-block'
  | 'math-block'
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

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const findInputRef = ref<HTMLInputElement | null>(null)
const highlightRef = ref<HTMLDivElement | null>(null)
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
const findBarOpen = ref(false)
const findQuery = ref('')
const replaceQuery = ref('')
const currentMatchIndex = ref(0)
const isMarkdown = computed(() => ['md', 'markdown'].includes((props.language || '').toLowerCase()))
const matches = computed(() => {
  if (!findQuery.value) {
    return []
  }
  const result: Array<{ start: number; end: number }> = []
  const haystack = model.value.toLowerCase()
  const needle = findQuery.value.toLowerCase()
  let cursor = 0
  while (cursor <= haystack.length) {
    const found = haystack.indexOf(needle, cursor)
    if (found < 0) {
      break
    }
    result.push({ start: found, end: found + findQuery.value.length })
    cursor = found + Math.max(1, needle.length)
  }
  return result
})

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const highlightedHtml = computed(() => {
  const content = model.value
  if (!findBarOpen.value || !findQuery.value || !content) {
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
    if (m.start > pos) {
      result += escapeHtml(content.slice(pos, m.start))
    }
    const cls = i === currentMatchIndex.value ? 'match-current' : 'match-highlight'
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

async function pasteFromClipboard() {
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

function syncScroll() {
  const ta = textareaRef.value
  const hl = highlightRef.value
  if (ta && hl) {
    hl.scrollTop = ta.scrollTop
    hl.scrollLeft = ta.scrollLeft
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
    case 'hr': insertBlock('---'); break
    case 'insert-code-block': insertBlock('```\n\n```', 4); break
    case 'math-block': insertBlock('$$\n\n$$', 3); break
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
  const sel = selectedRange()
  const isModifier = event.ctrlKey || event.metaKey
  if (!isModifier && !event.altKey && !props.readonly) {
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
  const key = event.key.toLowerCase()
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
  if (props.readonly) {
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
  activeMenuGroup.value = ''
}

onBeforeUnmount(() => {
  document.removeEventListener('click', closeContextMenu)
})
</script>

<template>
  <section class="code-editor">
    <div class="code-editor-header">
      <span>{{ language || 'text' }}</span>
      <span v-if="isMarkdown" class="code-editor-shortcuts">Ctrl+S 保存 · Ctrl+F 查找 · Ctrl+B/I/D 格式</span>
    </div>
    <div v-if="findBarOpen" class="find-replace-bar">
      <div class="find-field-wrapper">
        <div class="find-field-row">
          <input
            ref="findInputRef"
            v-model="findQuery"
            placeholder="查找"
            class="find-input"
            @keydown.enter.prevent="findNext"
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
    <div class="editor-wrapper">
      <div v-if="findBarOpen" ref="highlightRef" class="highlight-layer" v-html="highlightedHtml"></div>
      <textarea
        ref="textareaRef"
        v-model="model"
        class="code-editor-input"
        :class="{ readonly }"
        spellcheck="false"
        :readonly="readonly"
        @keydown.ctrl.s.prevent="$emit('save')"
        @keydown.meta.s.prevent="$emit('save')"
        @keydown="handleEditorKeydown"
        @input="flushTypingSnapshot"
        @scroll="syncScroll"
        @contextmenu="openContextMenu"
      ></textarea>
    </div>
    <div
      v-if="contextMenuOpen"
      class="markdown-context-menu"
      :style="contextMenuStyle"
      @click.stop
      @contextmenu.prevent
    >
      <div class="markdown-context-primary">
        <div
          v-for="group in menuGroups"
          :key="group.title"
          class="markdown-context-group"
          @mouseenter="activeMenuGroup = group.title"
        >
          <button
            class="markdown-context-parent"
            :class="{ active: activeMenuGroup === group.title }"
            type="button"
            @click.stop="activeMenuGroup = activeMenuGroup === group.title ? '' : group.title"
          >
            <span>{{ group.title }}</span>
            <span aria-hidden="true">›</span>
          </button>
          <div v-if="activeMenuGroup === group.title" class="markdown-context-submenu">
            <button
              v-for="item in group.items"
              :key="item.command"
              type="button"
              @click="runCommand(item.command)"
            >
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
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}

.code-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  height: 28px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.code-editor-shortcuts {
  overflow: hidden;
  color: var(--color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.find-replace-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8);
  border-bottom: 1px solid var(--color-border);
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

.highlight-layer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  padding: var(--space-12);
  font-family: var(--font-text);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
  tab-size: 2;
  white-space: pre;
  color: transparent;
  word-wrap: normal;
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

.markdown-context-menu {
  position: fixed;
  z-index: 1200;
  width: 148px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  box-shadow: var(--shadow-lg);
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.markdown-context-submenu {
  position: absolute;
  top: -6px;
  left: calc(100% + 8px);
  display: grid;
  min-width: 210px;
  max-height: min(360px, calc(100vh - 24px));
  overflow: auto;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  box-shadow: var(--shadow-lg);
}

.markdown-context-group button,
.markdown-context-submenu button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
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
  .code-editor-shortcuts {
    display: none;
  }

  .find-replace-actions {
    flex-wrap: wrap;
  }
}
</style>
