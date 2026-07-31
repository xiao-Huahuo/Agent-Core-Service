/*
 * Git API development proxy regression test.
 *
 * Usage:
 * Ensures Vite forwards `/git/*` requests to FastAPI instead of returning the
 * SPA index document, which cannot be parsed as an API JSON response.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const viteConfigSource = readFileSync(resolve(__dirname, '../../../vite.config.ts'), 'utf-8')

describe('Git API development proxy', () => {
  it('forwards Git API requests to the backend service', () => {
    expect(viteConfigSource).toContain("'/git': 'http://127.0.0.1:8002'")
  })
})
