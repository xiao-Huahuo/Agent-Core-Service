/**
 * Agent panel lazy-session creation regression tests.
 *
 * Usage:
 * Protects the UI boundary so the new-conversation action only opens a blank
 * draft and the existing ChatStore remains the sole first-turn creator.
 */
import { describe, expect, it } from 'vitest'

import agentPanelSource from '@/components/editor_workspace/AgentPanel.vue?raw'

function functionBody(name: string, nextName: string): string {
  return agentPanelSource.slice(
    agentPanelSource.indexOf(`function ${name}`),
    agentPanelSource.indexOf(`function ${nextName}`),
  )
}

describe('Agent panel session creation boundary', () => {
  it('opens a blank draft without creating or pruning a persisted session', () => {
    const body = functionBody('startNewConversationDraft', 'selectSession')

    expect(body).toContain('sessionStore.clearSelection()')
    expect(body).toContain('chatStore.value = useChatStore()')
    expect(body).toContain('chatStore.value.clear()')
    expect(body).not.toContain('sessionStore.create(')
    expect(body).not.toContain('sessionStore.pruneEmpty(')
  })

  it('delegates first-message session creation to ChatStore', () => {
    const body = functionBody('sendMessage', 'createTaskListFromInput')

    expect(body).toContain('await chatStore.value.send(')
    expect(body).not.toContain('sessionStore.create(')
  })
})
