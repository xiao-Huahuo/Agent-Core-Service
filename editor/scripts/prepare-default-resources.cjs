/*
 * Prepare install-time default resources for electron-builder.
 *
 * Usage:
 *   npm run prepare:default-resources
 *
 * The packaged defaults are intentionally not a full copy of resources/:
 * - mcp: copies only template files
 * - safety: copies defaults as-is
 * - skills: copies defaults as-is
 * - knowledge: creates an empty directory only
 */
/* eslint-disable @typescript-eslint/no-require-imports */

const fs = require('node:fs')
const path = require('node:path')

const editorRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(editorRoot, '..')
const sourceResources = path.join(projectRoot, 'resources')
const targetRoot = path.join(editorRoot, '.packaging', 'default-resources')

function copyDir(source, target) {
  if (!fs.existsSync(source)) {
    return
  }
  fs.cpSync(source, target, { recursive: true, force: true })
}

fs.rmSync(targetRoot, { recursive: true, force: true })
fs.mkdirSync(path.join(targetRoot, 'knowledge'), { recursive: true })

fs.mkdirSync(path.join(targetRoot, 'mcp'), { recursive: true })
for (const templateName of ['example.json']) {
  const source = path.join(sourceResources, 'mcp', templateName)
  if (fs.existsSync(source)) {
    fs.copyFileSync(source, path.join(targetRoot, 'mcp', templateName))
  }
}

copyDir(path.join(sourceResources, 'safety'), path.join(targetRoot, 'safety'))
copyDir(path.join(sourceResources, 'skills'), path.join(targetRoot, 'skills'))

console.log(`Prepared default resources: ${targetRoot}`)
