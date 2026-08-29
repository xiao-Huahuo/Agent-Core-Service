/**
 * Four-library unified search API client.
 *
 * Usage:
 * WorkspaceStore calls `searchAllLibraries` with the user's exact source and
 * capability selections. The backend performs title search unconditionally.
 */

import { apiGet } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { SearchSource, UnifiedSearchResponse } from '@/types/unifiedSearch'

/** Execute one user-scoped search without adding unselected sources. */
export function searchAllLibraries(
  userId: string,
  query: string,
  sources: SearchSource[],
  fulltext: boolean,
  semantic: boolean,
): Promise<UnifiedSearchResponse> {
  return apiGet<UnifiedSearchResponse>(API_ROUTES.UNIFIED_SEARCH, {
    user_id: userId,
    query,
    sources: sources.join(','),
    fulltext: fulltext ? 'true' : 'false',
    semantic: semantic ? 'true' : 'false',
  }, {
    timeoutMs: semantic ? 120_000 : 30_000,
  })
}
