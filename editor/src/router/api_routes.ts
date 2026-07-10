/*
 * API route registry for the editor front-end.
 *
 * Usage:
 * Import these constants from API clients and stores instead of hard-coding
 * endpoint strings inside components.
 */

export const API_ROUTES = {
  SETTINGS_PROFILE: '/settings/profile',
  SETTINGS_KNOWLEDGE_DIR: '/settings/profile/knowledge-dir',
  SETTINGS_SYSTEM_PROMPT: '/settings/system-prompt',
  SETTINGS_SYSTEM_PROMPT_ENTRIES: '/settings/system-prompt/entries',
  SETTINGS_MEMORIES: '/settings/memories',
  KNOWLEDGE_REBUILD: '/knowledge/rebuild',
  KNOWLEDGE_FILES: '/knowledge/files',
  KNOWLEDGE_FILE_CREATE: '/knowledge/files/file',
  KNOWLEDGE_FILE_CONTENT: '/knowledge/files/content',
  KNOWLEDGE_FILE_UPLOAD: '/knowledge/files/upload',
  KNOWLEDGE_FILE_FOLDER: '/knowledge/files/folder',
  KNOWLEDGE_FILE_COPY: '/knowledge/files/copy',
  KNOWLEDGE_FILE_RENAME: '/knowledge/files/rename',
  KNOWLEDGE_FILE_EVENTS: '/knowledge/files/events',
  KNOWLEDGE_INDEX_RUN: '/knowledge/index/run',
  KNOWLEDGE_INDEX_STATUS: '/knowledge/index/status',
  AGENT_STREAM: '/agent/stream',
  AGENT_STREAM_RUN: '/agent/stream-run',
  AGENT_CURRENT_DOCUMENT_CONTEXT: '/agent/editor-context/current-document',
  AGENT_TOOLS: '/agent/tools',
  AGENT_EVENTS: '/agent/events',
  AGENT_RECALL_DETAILS: '/agent/recall-details',
  KNOWLEDGE_SEARCH: '/knowledge/search',
  SETTINGS_MODEL_CONFIG: '/settings/model-config',
  SETTINGS_WEB_SEARCH: '/settings/web-search',
} as const
