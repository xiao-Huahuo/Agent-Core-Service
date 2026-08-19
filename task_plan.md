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

## Current Task: Password vault layout normalization

### Goal
Rebuild the unlocked vault page into a component-library-style left sidebar plus right-side toolbar/content layout, while adding the requested static form borders and preserving vault behavior.

### Phases
- [x] Inspect vault layout, sidebar, unlock form, item editor, and reference toolbar dimensions.
- [x] Move the vault title into the sidebar, remove the sidebar filter heading, and place the toolbar only on the right.
- [x] Apply the static translucent borders and normalize right-toolbar controls to the existing 44px/28px standard.
- [x] Review the diff and run the requested proportionate verification.

### Acceptance mapping
- [x] Unlock/create-master-password form has the translucent form border.
- [x] Vault item form keeps the translucent form border.
- [x] Vault sidebar has no drop shadow and has the translucent border.
- [x] Sidebar buttons retain the component-library sidebar interaction style.
- [x] Sidebar no longer displays the “筛选” heading.
- [x] “密码库” title moves into the sidebar and the toolbar stays on the right.
- [x] Right toolbar follows the existing 44px topbar and 28px control standard.

### Status
**Complete** - vault layout, sidebar, forms, toolbar normalization, targeted tests, build, and Chromium smoke verification are finished.

## Current Task: Vault toggle and table visual parity

### Goal
Move the vault mode toggle to the left side of the right-hand toolbar and restyle the vault table to match the pasted reference table surface without adding React/TanStack dependencies or fake data.

### Phases
- [x] Inspect the pasted reference and current VaultTable structure.
- [x] Split the vault toggle from right-side actions and keep those actions right-aligned.
- [x] Rebuild VaultTable’s visual shell, header, rows, selection state, and footer styling around existing vault data/events.
- [x] Run focused checks, build, and UI smoke verification.

### Acceptance mapping
- [x] Vault mode toggle is left-aligned in the right toolbar.
- [x] Existing vault actions remain right-aligned with no separator.
- [x] Vault table visually follows the pasted reference’s bordered rounded surface, header, rows, selection, and footer rhythm.
- [x] Existing open, toggle, context, filter, and vault data behavior remains connected.

### Status
**Complete** - toggle placement and table visual parity are implemented and verified.

## Current Task: Library topbar typography normalization

### Goal

Normalize all visible text controls in the five pages under the 库 menu to the 12px scaled size used by the FileResourceManager top-left page toggle.

### Acceptance mapping

- [x] Identify the five target pages and the exact 12px scaled reference size.
- [ ] Normalize the FileResourceManager, LibraryView, ComponentLibraryView, VaultView, and SmartFormsView topbar text.
- [ ] Run build/type checks and actual Chromium smoke verification for all five pages.

### Status

**In progress** - target surfaces and current typography differences are identified; implementation is next.

## Current Task: Cross-form input and height-motion normalization

### Goal

Apply the established gray input surface, borderless focus ring, and smooth form-height transition behavior to the requested library, component-library, vault, smart-table, task-queue, feedback, and settings forms.

### Acceptance mapping

- [x] Normalize the three other library forms.
- [x] Normalize the component-library upload form.
- [x] Normalize the vault new-password form.
- [x] Normalize the smart-table create form.
- [x] Normalize the task-queue create form.
- [x] Normalize the five task-queue task forms.
- [x] Normalize the user feedback form.
- [x] Normalize all settings-page input controls.
- [x] Add smooth height adaptation wherever a form switches between internal states.
- [x] Do not change business/API behavior.

### Phases

- [x] Phase 1: Inventory target pages, forms, and existing reusable input/transition styles.
- [x] Phase 2: Add the shared input surface and focus-ring primitives.
- [x] Phase 3: Apply primitives to all requested forms and state-switching containers.
- [x] Phase 4: Review the diff and record that verification was skipped per user request.

### Key questions

1. Which “other three library forms” are concrete components in the current codebase?
2. Which task-queue controls render the five task-specific forms?
3. Which forms already have a height transition that can be reused instead of duplicated?

### Decisions made

- Keep the current library source-mode measured-height implementation as the reference motion pattern.
- Prefer one shared CSS primitive plus narrow component selectors over broad global selectors that could alter unrelated controls.
- Preserve existing input-specific dimensions and only normalize background, border, focus ring, and state-container height motion.

### Status

**Complete** - all requested form surfaces and applicable state-height transitions are wired; no tests or servers were run per the user’s standing instruction.
