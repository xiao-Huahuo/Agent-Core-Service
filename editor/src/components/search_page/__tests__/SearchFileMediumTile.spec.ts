/** Search file medium-tile narrow-layout visual contract tests. */

import { describe, expect, it } from 'vitest'
import source from '@/components/search_page/SearchFileMediumTile.vue?raw'

describe('SearchFileMediumTile narrow layout', () => {
  it('reserves two title lines, enlarges the icon, and de-emphasizes file size', () => {
    expect(source).toMatch(/\.material-file-icon-medium\s*\{[^}]*width: 52px;[^}]*height: 52px;/s)
    expect(source).toMatch(/\.tile-name\s*\{[^}]*-webkit-line-clamp: 2;/s)
    expect(source).toMatch(/small\s*\{[^}]*font-size: calc\(10px \* var\(--font-scale\)\);/s)
  })
})
