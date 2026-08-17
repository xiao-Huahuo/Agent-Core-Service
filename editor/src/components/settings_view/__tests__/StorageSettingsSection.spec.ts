/*
 * 存储设置只读路径契约。
 *
 * Usage:
 * 防止 `.mw` 托管目录或运行时根目录重新出现可编辑入口，并确保图书馆旧默认值
 * 不会回退到知识库顶层的 `library/`。
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('storage settings path contract', () => {
  it('only edits the active knowledge root and keeps managed/runtime paths read-only', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/settings_view/StorageSettingsSection.vue'), 'utf8')

    expect(source).toContain('v-model="knowledgeDirDraft"')
    expect(source).not.toContain('libraryStorageDirDraft')
    expect(source).not.toContain('baseDataDirDraft')
    expect(source).not.toContain('handleSaveLibraryStorageDir')
    expect(source).not.toContain('handleSaveBaseDataDir')
    expect(source).toContain("item.entry.can_clear && item.entry.key === 'trash_dir'")
  })

  it('uses the fixed managed library directory as the frontend fallback', () => {
    const settingsStore = readFileSync(resolve(process.cwd(), 'src/stores/settings.ts'), 'utf8')
    const libraryView = readFileSync(resolve(process.cwd(), 'src/views/LibraryView.vue'), 'utf8')

    expect(settingsStore).toContain("library.library_storage_dir ?? '.mw/library'")
    expect(libraryView).toContain("libraryStorageDir || '.mw/library'")
  })
})
