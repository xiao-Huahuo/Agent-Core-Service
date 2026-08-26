/*
 * Smart-table column presentation metadata.
 *
 * Usage:
 * SmartFormsView uses these stable labels and local Material icon names for
 * column headers and every add-column menu.
 */

import type { SmartColumn, SmartColumnType } from '@/components/smart_forms/smartLiteratureTable'

/** User-facing labels shown in compact column-type pills. */
export const SMART_COLUMN_TYPE_LABELS: Record<SmartColumnType, string> = {
  index: '索引',
  file: '文件',
  readonly_text: '只读文本',
  text: '文本',
  smart_text: '智能文本',
  tag: '标签',
  smart_tag: '智能标签',
  boolean: '是/否',
  star: '星级',
  date: '日期',
}

/** Local Material icons used for user-created fields of each type. */
export const SMART_COLUMN_TYPE_ICONS: Record<SmartColumnType, string> = {
  index: 'checklist',
  file: 'upload',
  readonly_text: 'visibility',
  text: 'text-fields',
  smart_text: 'auto-awesome',
  tag: 'label',
  smart_tag: 'psychology',
  boolean: 'check-circle',
  star: 'star',
  date: 'event',
}

/** Every built-in field has its own icon so fields remain recognizable at a glance. */
export const BUILTIN_COLUMN_ICONS: Record<string, string> = {
  row_index: 'checklist',
  literature_file: 'upload',
  literature_content: 'document',
  figures: 'image',
  formulas: 'calculate',
  title: 'title',
  paper_type: 'book',
  rating: 'star',
  reading_progress: 'schedule',
  keywords: 'label',
  abstract: 'view-stream',
  journal: 'archive',
  authors: 'group',
  year: 'calendar',
  why: 'psychology',
  what: 'manage-search',
  how: 'build',
  result: 'fact-check',
  innovation: 'auto-awesome',
  limitations: 'warning',
  future_work: 'arrow-right',
  doi: 'link',
  url: 'language',
}

/** Resolves the icon for either a built-in or a user-created column. */
export function smartColumnIcon(column: Pick<SmartColumn, 'id' | 'type'>): string {
  return BUILTIN_COLUMN_ICONS[column.id] || SMART_COLUMN_TYPE_ICONS[column.type]
}

/** Resolves the localized type label for a column. */
export function smartColumnTypeLabel(type: SmartColumnType): string {
  return SMART_COLUMN_TYPE_LABELS[type]
}
