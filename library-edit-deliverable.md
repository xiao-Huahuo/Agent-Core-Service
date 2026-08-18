# Library edit form content panel

## Implemented

- Added `LibraryRealContentPanel.vue` for file, image, URL, plain-text, and code sources.
- Added the bottom-left animated 元信息/元文件 toggle to `LibraryItemDialog.vue`.
- Reused `CompactCodeInput.vue`; text/code changes save through `writeKnowledgeFile`.
- Kept collections metadata-only, opened files in the editor, and opened URLs in the browser sidebar.
- Removed the real-content header divider, corrected the URL action icon, and aligned create-form text/code surfaces with the description field.

## Verification

- `npm run build-only`: passed.
- Targeted type-check filter: no errors from the new real-content component.
- Node Playwright smoke flow: passed for all five source kinds, left-cover/right-content layout, URL action, and text/code loading.
- Repository-wide `npm run type-check`: remains blocked by pre-existing unrelated errors listed in the task notes.
