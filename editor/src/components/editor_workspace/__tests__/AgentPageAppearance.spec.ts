/**
 * Agent page workspace appearance regression tests.
 *
 * Usage:
 * Verifies the full-page Agent uses the shared workspace card frame and keeps
 * a native draggable scrollbar on the message list.
 */
import { describe, expect, it } from 'vitest'

import messageListSource from '@/components/editor_workspace/agent_chat/MessageList.vue?raw'
import sessionDrawerSource from '@/components/editor_workspace/agent_chat/SessionDrawer.vue?raw'
import editorWorkspaceSource from '@/views/EditorWorkspace.vue?raw'

describe('Agent page workspace appearance', () => {
  it('shows a draggable vertical scrollbar for the chat history', () => {
    expect(messageListSource).toMatch(/\.message-list \{[^}]*overflow-y: auto;[^}]*scrollbar-width: thin;/s)
    expect(messageListSource).toMatch(/\.message-list::-webkit-scrollbar \{[^}]*width: 10px;/s)
    expect(messageListSource).not.toContain('scrollbar-width: none')
    expect(messageListSource).not.toMatch(/\.message-list::-webkit-scrollbar \{[^}]*display: none;/s)
  })

  it('keeps the shared four-pixel translucent workspace frame on Agent page', () => {
    expect(editorWorkspaceSource).toMatch(
      /\.main-shell\.ide-panel,[\s\S]*?\.agent-col \{[^}]*border: 1px solid var\(--workspace-panel-border\);[^}]*box-shadow: 0 0 0 4px var\(--workspace-panel-ring\);/s,
    )
    expect(editorWorkspaceSource).not.toMatch(
      /\.main-shell\.ide-panel\.agent-page-main-shell \{[^}]*(?:border: 0|box-shadow: none);/s,
    )
  })

  it('uses the workspace card radius on the Agent session sidebar', () => {
    expect(sessionDrawerSource).toMatch(
      /\.session-drawer\.page-mode \{[^}]*border-radius: var\(--workspace-card-radius\);/s,
    )
    expect(sessionDrawerSource).not.toMatch(
      /\.session-drawer\.page-mode(?:\.open)? \{[^}]*border-radius: 0;/s,
    )
  })
})
