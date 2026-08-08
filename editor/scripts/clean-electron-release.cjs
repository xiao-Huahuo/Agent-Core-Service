/*
 * Clean stale electron-builder output before Windows packaging.
 *
 * Usage:
 *   npm run clean:electron-release
 *
 * electron-builder renames release/win-unpacked.tmp to release/win-unpacked.
 * On Windows that rename fails with EPERM when an old unpacked app is still
 * present or locked, so remove only those generated directories up front.
 */
/* eslint-disable @typescript-eslint/no-require-imports */

const fs = require('node:fs')
const path = require('node:path')

const editorRoot = path.resolve(__dirname, '..')
const releaseRoot = path.join(editorRoot, 'release')
const generatedDirs = [
  path.join(releaseRoot, 'win-unpacked'),
  path.join(releaseRoot, 'win-unpacked.tmp'),
]

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function removeWithRetry(dir) {
  let lastError = null
  for (let attempt = 1; attempt <= 15; attempt += 1) {
    try {
      fs.rmSync(dir, { recursive: true, force: true })
      return
    } catch (error) {
      lastError = error
      await sleep(1000)
    }
  }
  const reason = lastError && lastError.message ? lastError.message : String(lastError)
  throw new Error(
    `Cannot remove generated package directory: ${dir}\n` +
    `Close any running MetaWeave/Electron window and close Explorer windows opened inside editor/release, then retry.\n` +
    `Original error: ${reason}`,
  )
}

async function main() {
  for (const dir of generatedDirs) {
    await removeWithRetry(dir)
  }
  console.log('Cleaned electron release staging directories.')
}

void main()
