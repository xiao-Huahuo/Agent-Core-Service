# Cross-form input and height-motion normalization

## Delivered

- Added shared `form-input-surface` styling: gray surface, no thin border, and translucent focus ring.
- Added shared `FormHeightTransition` for smooth natural-height changes.
- Applied the style to the requested library, component-library, vault, smart-table, task-queue, feedback, and settings form controls.
- Applied height motion to library source/edit states, vault setup/reset states, feedback state/list changes, settings tabs, and task-queue task states.

## Scope note

- Checkbox, radio, range, color, and file controls retain their specialized native/custom appearance.
- Business behavior and API contracts were not changed.
- Verification was skipped at the user’s explicit request.
