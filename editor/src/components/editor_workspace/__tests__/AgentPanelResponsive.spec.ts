/**
 * Agent sidebar responsive-layout regression tests.
 *
 * Usage:
 * Ensures panel mode activates compact rendering for mounted files, change
 * summaries, and the input toolbar instead of squeezing full-page content.
 */
import { describe, expect, it } from 'vitest'

import agentPanelSource from '@/components/editor_workspace/AgentPanel.vue?raw'
import chatInputSource from '@/components/editor_workspace/agent_chat/ChatInput.vue?raw'
import messageListSource from '@/components/editor_workspace/agent_chat/MessageList.vue?raw'

describe('Agent sidebar responsive layout', () => {
  it('passes compact mode to both the message list and input', () => {
    expect(agentPanelSource.match(/:compact="props\.mode === 'panel'"/g)).toHaveLength(2)
  })

  it('reduces mounted-file metadata in panel mode', () => {
    expect(agentPanelSource).toMatch(
      /\.agent-panel:not\(\.agent-page-mode\) :deep\(\.agent-mounted-file\) \{[^}]*width: 100%;[^}]*min-height: 54px;[^}]*height: auto;/s,
    )
    expect(agentPanelSource).toMatch(
      /:deep\(\.agent-mounted-file__path\),[\s\S]*?:deep\(\.agent-mounted-file__created\),[\s\S]*?:deep\(\.agent-mounted-file__statuses\) \{\s*display: none;/s,
    )
  })

  it('uses icon-only compact controls without toolbar overlap', () => {
    expect(chatInputSource).toContain(':class="{ centered, compact }"')
    expect(chatInputSource).toMatch(
      /\.chat-input-wrap\.compact \.model-config-trigger span,[\s\S]*?\.access-mode-caret \{\s*display: none;/s,
    )
    expect(chatInputSource).toMatch(/\.chat-input-wrap\.compact \.input-toolbar \{[^}]*gap: 2px;/s)
  })

  it('routes post-turn suggestions through the message list instead of the input', () => {
    expect(agentPanelSource).toMatch(/<MessageList[\s\S]*?:suggestions="chatStore\.taskSuggestions"[\s\S]*?@select-suggestion="sendSuggestion"/s)
    expect(agentPanelSource).not.toMatch(/<ChatInput[\s\S]*?:suggestions="chatStore\.taskSuggestions"/s)
    expect(chatInputSource).not.toContain('task-suggestions')
  })

  it('uses the composer top edge as the message viewport bottom', () => {
    expect(agentPanelSource).toMatch(
      /\.chat-content :deep\(\.chat-input-wrap:not\(\.centered\)\) \{[^}]*position: relative;[^}]*bottom: auto;[^}]*flex: 0 0 auto;/s,
    )
    expect(messageListSource).not.toMatch(/padding-bottom: (?:108|116)px;/)
  })

  it('hands bottom pinning from streaming into the completed turn layout', () => {
    expect(messageListSource).toMatch(
      /watch\(\(\) => props\.isStreaming,[\s\S]*?!isStreaming && wasStreaming[\s\S]*?schedulePinnedScroll/,
    )
    expect(messageListSource).toContain('scheduledRevision !== userScrollRevision')
  })
})
