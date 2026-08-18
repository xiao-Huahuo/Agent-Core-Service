# Task Plan: Library edit form metadata/content toggle

## Goal
Add a bottom-left 元信息/元文件 toggle to the edit dialog and render each real-content type with the requested read/edit/open behavior while preserving the existing metadata form.

## Acceptance mapping
- [x] Toggle exists at the bottom left, animates, and switches between 元信息 and 元文件.
- [x] 元信息 shows the existing edit metadata fields unchanged.
- [x] File content shows a centered large resource-explorer-style file item and opens the editor when clicked.
- [x] Image content is displayed directly and is read-only.
- [x] Web URL content shows a read-only URL field and an open-in-new action that opens the browser sidebar.
- [x] Plain text content is shown in an editable text box and saves through the existing file API.
- [x] Code content uses the same editable code component as the create form and saves through the existing file API.
- [x] Cover remains on the left in 元文件 mode.
- [x] Collection editing remains metadata-only and does not expose unsupported real-content controls.

## Phases
- [x] Phase 1: Inspect existing data fields, editor entry points, and reusable code component.
- [x] Phase 2: Implement reusable real-content panel and dialog toggle.
- [x] Phase 3: Wire save/open behavior and preserve collection behavior.
- [x] Phase 4: Run targeted checks and record remaining risks.

## Key Questions
1. How are file, image, URL, plain text, and code distinguished in LibraryItem?
2. Which existing component and workspace action should be reused for code and file editing?

## Decisions Made
- Keep metadata editing in the existing LibraryItemDialog and add the content view alongside it.
- Use existing CompactCodeInput and workspaceStore.selectFile/openBrowserSidebar APIs instead of introducing new backend routes.

## Errors Encountered
- Python Playwright was unavailable; the same smoke flow was run with the project's installed Node Playwright package.
- The repository-wide type check reports pre-existing errors in unrelated files; no error remains for `LibraryRealContentPanel.vue` after correction.

## Status
**Complete** - implementation, build, targeted type filtering, and interface smoke verification are finished.
