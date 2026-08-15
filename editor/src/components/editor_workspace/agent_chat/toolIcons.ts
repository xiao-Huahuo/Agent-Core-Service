/*
 * Agent tool category icon mapping.
 *
 * Each backend tool family shares one semantic name from the locally bundled
 * IcIcon asset set. Unknown extension tools use the utility wrench fallback.
 */

/** Groups registered backend tools by the local icon used in Agent rows. */
const TOOL_ICON_GROUPS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['build', ['list_available_tools', 'get_current_time', 'run_terminal_command', 'download_file']],
  ['git', [
    'git_status', 'git_diff', 'git_history', 'git_init_repository', 'git_restore_files',
    'git_commit_files', 'git_push_branch', 'git_create_branch', 'git_add_remote',
    'git_switch_branch', 'git_pull_branch',
  ]],
  ['auto-awesome', ['list_skills', 'use_skill']],
  ['psychology', [
    'get_long_term_memory', 'write_long_term_memory', 'write_long_term_rule',
    'delete_long_term_memory', 'delete_long_term_rule',
  ]],
  ['manage-search', [
    'get_knowledge_context', 'rebuild_knowledge_base', 'search_knowledge',
    'save_uploaded_attachment_to_knowledge', 'get_knowledge_file_url',
  ]],
  ['document', [
    'get_current_viewing_document', 'list_knowledge_files', 'read_knowledge_file',
    'read_multimodal_file_info', 'write_knowledge_file', 'patch_knowledge_file',
    'show_markdown_html', 'delete_knowledge_file', 'rename_knowledge_file',
    'create_knowledge_folder',
  ]],
  ['book', [
    'list_library_items', 'list_library_tags', 'add_library_book', 'add_library_collection',
    'update_library_item', 'remove_library_item',
  ]],
  ['checklist', [
    'get_task_list_status', 'create_task_list', 'complete_task_list_item', 'finish_task_list',
  ]],
  ['group', ['spawn_child_agent', 'wait_for_child_agents']],
  ['todo', ['list_todos', 'add_todo', 'add_automation', 'toggle_todo', 'edit_todo', 'delete_todo']],
  ['language', ['web_search', 'web_image_search']],
]

/** Provides constant-time icon lookup while keeping the category list readable. */
const TOOL_ICON_BY_NAME = new Map(
  TOOL_ICON_GROUPS.flatMap(([iconName, toolNames]) => toolNames.map((toolName) => [toolName, iconName])),
)

/** Returns a locally bundled IcIcon name for a registered or extension tool. */
export function toolIconName(toolName: string): string {
  return TOOL_ICON_BY_NAME.get(toolName) ?? 'build'
}
