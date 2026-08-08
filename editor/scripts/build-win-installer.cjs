/*
 * Build the Windows NSIS installer into a fresh output directory.
 *
 * Usage:
 *   npm run build:win-installer
 *
 * electron-builder uses release/win-unpacked as a staging directory by default.
 * On Windows, stale app.asar files can remain locked by Explorer, antivirus, or
 * indexers. A per-build output directory avoids reusing that locked path.
 */
/* eslint-disable @typescript-eslint/no-require-imports */

const childProcess = require('node:child_process')
const path = require('node:path')

function timestamp() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    '-',
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join('')
}

const outputDir = path.join('release', `build-${timestamp()}`)
const electronBuilderCli = path.resolve(__dirname, '..', 'node_modules', 'electron-builder', 'cli.js')
const result = childProcess.spawnSync(
  process.execPath,
  [electronBuilderCli, '--win', 'nsis', `--config.directories.output=${outputDir}`],
  {
    cwd: path.resolve(__dirname, '..'),
    stdio: 'inherit',
  },
)

if (result.error) {
  throw result.error
}

process.exitCode = result.status ?? 1
