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

## Current task: Password vault UI

- `VaultView.vue` currently renders `.vault-topbar` above `.vault-main`; the title and filter toggle live in that topbar.
- `VaultFilterPanel.vue` currently owns the sidebar shell, its `筛选` heading, search, type buttons, and tag buttons.
- `VaultItemEditor.vue` already uses `library-form-surface`, so its translucent border and scan behavior are already present.
- `VaultUnlockPanel.vue` uses `.unlock-card` without the shared translucent ring; add only the ring, not the scanning class.
- Resource toolbar standard is `44px` minimum height, `8px 12px` padding, and `28px` controls; library/component-library work has been aligned to the same values.
- The requested layout requires a vault grid: fixed sidebar on the left, then a right column containing the toolbar and table.
- `VaultFilterPanel.spec.ts`: targeted test passes after updating the shell expectation to the static translucent border.
- `npm run build-only`: passed.
- `npm run test:e2e -- e2e/vue.spec.ts --project=chromium`: 2 tests passed; no new test file was added.

## Current task: Vault toggle and table visual parity

- Reference table uses a rounded bordered outer surface, a compact toolbar, `h-11` header cells, hover-transparent header rows, separated body rows, selection state, and a footer with page-size/count/pagination controls.
- Current `VaultTable.vue` is a bare table with 42px cells and no outer surface or footer; it already emits `open`, `toggle`, and `context` and must keep those event contracts.
- Current `VaultView.vue` keeps the mode toggle inside `.top-actions`; the toggle must become the left sibling while actions stay right-aligned.
- `VaultTable.vue` now keeps the existing row events and data while adding a client-side page-size/footer surface; no external table dependency or fake data was introduced.
- Focused VaultFilterPanel test: 3 passed; `npm run build-only`: passed; Chromium smoke: 2 passed.

# Notes: Cross-form input and height-motion normalization

## User scope

- Apply the established gray, borderless input surface and translucent focus ring.
- Apply smooth form-height adaptation for state-switching forms.
- Targets: the other three library forms, component-library upload form, vault new-password form, smart-table create form, task-queue create form, five task-queue task forms, user feedback form, and all settings-page inputs.
- User explicitly requested that this round not run tests.

## Reference implementation

- `editor/src/components/library_view/LibraryCreateDialog.vue` now owns the measured source-mode height transition in `sourceModeZone` and the normalized input surface styles.

## Inventory findings

- Library forms are `LibraryCreateDialog.vue`, `LibraryItemDialog.vue`, and `LibraryRealContentPanel.vue`; `LibraryTagPicker.vue` is shared by the library and component-library forms.
- Component upload is `ComponentUploadForm.vue`; its code panel and component-name input use the shared surface.
- Vault forms are `VaultUnlockPanel.vue` and `VaultPasswordResetDialog.vue`.
- Smart-table creation lives in `SmartFormsView.vue`; task queue forms are all rendered by `AgentQueueTaskDialog.vue` for pending, running, review, confirmed, and terminated tasks.
- Feedback is `FeedbackPopover.vue`; settings inputs are covered at the `SettingsView.vue` page boundary while excluding toggle/range/color/file controls.

## Implementation findings

- Added `FormHeightTransition.vue` and reused it for library source/edit modes, vault setup mode, feedback state/list changes, and settings tabs.
- Task queue uses direct height measurement on the existing dialog because its template is intentionally compressed and already exposes one dialog root.
- No business/API behavior was changed. Tests and servers were intentionally skipped per user request.
