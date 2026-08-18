# Notes: Library edit form metadata/content toggle

## Existing implementation

- `LibraryItemDialog.vue` currently edits title, description, cover mode, tags, and cover upload.
- `LibraryCreateDialog.vue` already uses `CompactCodeInput` for script content.
- `LibraryView.vue` currently opens files through `workspaceStore.selectFile`, and opens web URLs through `workspaceStore.openBrowserSidebar`.
- Collections and books share `LibraryItemDialog`; collections have no real source content.
- `LibraryItem` already carries `content_type`, `source_mime`, `source_path`, `source_url`, `source_name`, and `source_exists`.
- `readKnowledgeFile(userId, path)` is the existing text-content endpoint; no new API route is required.
- `buildApiUrl('/knowledge/files/raw', { user_id, path })` is already used for source-image rendering.
- `CompactCodeInput.vue` is the existing code-box component used by the create form.
- `workspaceStore.selectFile` opens the editor and `workspaceStore.openBrowserSidebar` opens the right browser sidebar.

## Pending findings
- Classify URL from `content_type === 'web_url'`, image from `source_mime`/image extension, code from common code MIME/extensions, and the remaining text-like source as plain text.
- Render source file itself as a centered large file tile; only text/code require a read request.
- Text and code drafts are emitted to the parent dialog and persisted with the existing knowledge-file write API on Save; images and URLs remain read-only.
- The real-content header intentionally has no divider, the URL action uses the existing `open-in-new` icon, and the bottom mode toggle uses a sliding active capsule.
