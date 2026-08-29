/*
 * Shared model lifecycle banner presentation state.
 *
 * Usage:
 * ModelLifecycleOverlay owns banner timing; TopCommandBar reads the compact
 * state and calls requestModelLifecycleExpansion() when its loader is clicked.
 */
import { reactive } from 'vue'

export const modelLifecycleUi = reactive({
  compact: false,
  hasNotices: false,
  expansionRequest: 0,
})

/** Ask the global model overlay to expand its current independent banners. */
export function requestModelLifecycleExpansion() {
  modelLifecycleUi.expansionRequest += 1
}
