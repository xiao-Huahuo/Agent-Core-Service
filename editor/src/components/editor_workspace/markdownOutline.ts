/*
 * Markdown heading outline helpers.
 *
 * Usage:
 * Parse ATX headings into a nested tree, filter it for the outline search,
 * and resolve the heading that owns a source caret offset.
 */

export interface MarkdownOutlineItem {
  id: string
  text: string
  level: number
  offset: number
  children: MarkdownOutlineItem[]
}

/** Builds a heading tree while ignoring heading-like text inside fenced code blocks. */
export function parseMarkdownOutline(content: string): MarkdownOutlineItem[] {
  const roots: MarkdownOutlineItem[] = []
  const stack: MarkdownOutlineItem[] = []
  const lines = content.split('\n')
  let offset = 0
  let fence = ''

  for (const line of lines) {
    const fenceMatch = line.match(/^\s*(`{3,}|~{3,})/u)
    if (fenceMatch) {
      const marker = fenceMatch[1]![0]!
      if (!fence) fence = marker
      else if (fence === marker) fence = ''
      offset += line.length + 1
      continue
    }

    const match = fence ? null : line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*$/u)
    if (match) {
      const level = match[1]!.length
      const item: MarkdownOutlineItem = {
        id: `heading-${offset}`,
        text: match[2]!.replace(/\s+#+\s*$/u, '').trim(),
        level,
        offset,
        children: [],
      }
      while (stack.length && stack[stack.length - 1]!.level >= level) stack.pop()
      const parent = stack[stack.length - 1]
      if (parent) parent.children.push(item)
      else roots.push(item)
      stack.push(item)
    }
    offset += line.length + 1
  }

  return roots
}

/** Returns headings in source order, regardless of nesting. */
export function flattenMarkdownOutline(items: MarkdownOutlineItem[]): MarkdownOutlineItem[] {
  return items.flatMap((item) => [item, ...flattenMarkdownOutline(item.children)])
}

/** Keeps matching headings and their ancestor paths for outline search. */
export function filterMarkdownOutline(items: MarkdownOutlineItem[], query: string): MarkdownOutlineItem[] {
  const needle = query.trim().toLocaleLowerCase()
  if (!needle) return items
  return items.flatMap((item) => {
    const children = filterMarkdownOutline(item.children, needle)
    if (!item.text.toLocaleLowerCase().includes(needle) && children.length === 0) return []
    return [{ ...item, children }]
  })
}

/** Resolves the last heading at or before the current source caret. */
export function headingAtOffset(items: MarkdownOutlineItem[], offset: number): MarkdownOutlineItem | null {
  let active: MarkdownOutlineItem | null = null
  for (const item of flattenMarkdownOutline(items)) {
    if (item.offset > offset) break
    active = item
  }
  return active
}

/** Collects every expandable key for the expand-all control. */
export function expandableHeadingIds(items: MarkdownOutlineItem[]): string[] {
  return items.flatMap((item) => item.children.length
    ? [item.id, ...expandableHeadingIds(item.children)]
    : [])
}

/** Returns the expandable ancestor keys needed to reveal one heading. */
export function headingAncestorIds(items: MarkdownOutlineItem[], id: string): string[] {
  for (const item of items) {
    if (item.id === id) return []
    const childPath = headingAncestorIds(item.children, id)
    if (childPath.length || item.children.some((child) => child.id === id)) {
      return [item.id, ...childPath]
    }
  }
  return []
}
