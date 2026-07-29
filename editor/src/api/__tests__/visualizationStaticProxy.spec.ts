/*
 * Visualization static asset delivery tests.
 *
 * Usage:
 * Verifies that Agent-generated runtime HTML can be loaded by iframe both in
 * Vite development mode and in the packaged app CSP.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const viteConfigSource = readFileSync(resolve(__dirname, '../../../vite.config.ts'), 'utf-8')

describe('visualization static delivery', () => {
  it('proxies runtime visualization HTML through Vite dev server', () => {
    expect(viteConfigSource).toContain("'/visualizations'")
    expect(viteConfigSource).toContain('http://127.0.0.1:8002')
  })

  it('allows backend-served visualization HTML in iframe CSP', () => {
    expect(viteConfigSource).toContain('frame-src')
    expect(viteConfigSource).toContain('http://127.0.0.1:8002')
    expect(viteConfigSource).toContain('http://localhost:8002')
  })
})
