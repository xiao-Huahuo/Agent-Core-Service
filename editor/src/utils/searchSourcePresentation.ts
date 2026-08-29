/**
 * Shared visual identity for searchable libraries.
 *
 * Usage:
 * SearchPalette, SearchPage, and the ActivityBar library menu reuse these icon
 * names and global color-token classes so the same library always looks alike.
 */

import type { SearchSource } from '@/types/unifiedSearch'

export interface SearchSourcePresentation {
  /** Human-readable library name. */
  label: string
  /** IcIcon semantic icon name. */
  icon: string
  /** Global CSS custom property holding the source color. */
  color: string
}

export const SEARCH_SOURCE_PRESENTATION: Record<SearchSource, SearchSourcePresentation> = {
  files: { label: '文件库', icon: 'folder-open', color: 'var(--color-search-files)' },
  library: { label: '图书馆', icon: 'book', color: 'var(--color-search-library)' },
  components: { label: '组件库', icon: 'grid-view', color: 'var(--color-search-components)' },
  literature: { label: '文献库', icon: 'document', color: 'var(--color-search-literature)' },
}
