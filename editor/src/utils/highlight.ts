/*
 * Text highlight helper.
 *
 * Usage:
 * Wraps case-insensitive matches of `query` in <mark> tags.
 * Callers must use v-html to render the returned string.
 */

export function highlightMatch(text: string, query: string): string {
  if (!query.trim() || !text) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const escapedQuery = escapeHtml(query.trim())
  const re = new RegExp(`(${escapeRegExp(escapedQuery)})`, 'gi')
  return escaped.replace(re, '<mark>$1</mark>')
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
