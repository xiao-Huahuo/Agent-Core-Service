/**
 * Component library domain types.
 *
 * Usage:
 * Shared by the API client, component grid, upload form, and preview compiler.
 */

export const COMPONENT_TAGS = [
  'buttons',
  'checkboxes',
  'toggle switches',
  'cards',
  'loaders',
  'inputs',
  'radio buttons',
  'forms',
  'patterns',
  'tooltips',
  'any',
] as const

export type ComponentTag = (typeof COMPONENT_TAGS)[number]
export type ComponentSourceFormat = 'vue' | 'html'

export interface ComponentLibraryItem {
  /** Stable database or bundled-resource identifier. */
  component_id: string
  /** User whose view requested the card. */
  user_id: string
  /** Human-readable filename or generated upload title. */
  title: string
  /** Exactly one fixed component category. */
  tag: ComponentTag
  /** Compiler selected for the source. */
  source_format: ComponentSourceFormat
  /** Original source copied by the user and compiled in the preview. */
  source: string
  /** Compatibility field; knowledge-directory component files are always false. */
  builtin: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ComponentLibraryResponse {
  /** Visible component cards. */
  components: ComponentLibraryItem[]
  /** Fixed tags returned by the server contract. */
  tags: ComponentTag[]
}

export interface ComponentLibraryCreatePayload {
  /** Owner of the durable upload. */
  user_id: string
  /** Vue SFC or standalone HTML source. */
  source: string
  /** The component's only category. */
  tag: ComponentTag
  /** Optional original basename preserved for file-picker uploads. */
  filename?: string
}

export interface ComponentLibraryRenamePayload {
  /** Owner whose active knowledge library contains the component file. */
  user_id: string
  /** Current path relative to the knowledge components directory. */
  component_id: string
  /** New visible basename without a required extension. */
  title: string
}

export interface ComponentLibraryUpdatePayload {
  /** Optional replacement source persisted to the same canonical file. */
  source?: string
  /** Optional replacement title, which may rename the canonical file. */
  title?: string
  /** Optional replacement fixed category. */
  tag?: ComponentTag
}
