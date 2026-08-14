/*
 * Unified menu integration regression tests.
 *
 * Usage:
 * Guards every workspace menu migrated to the shared Reka dropdown or shared
 * pointer-positioned context-menu surface requested by the editor UI.
 */
import { describe, expect, it } from 'vitest'

import mainSource from '@/main.ts?raw'
import SmartFormsSource from '@/views/SmartFormsView.vue?raw'
import VaultSource from '@/views/VaultView.vue?raw'
import AgentPanelSource from '@/components/editor_workspace/AgentPanel.vue?raw'
import CodeEditorSource from '@/components/editor_workspace/CodeEditor.vue?raw'
import SessionDrawerSource from '@/components/editor_workspace/agent_chat/SessionDrawer.vue?raw'
import LibraryTagPickerSource from '@/components/library_view/LibraryTagPicker.vue?raw'
import QueueDropdownSource from '@/components/agent_queue/QueueDropdown.vue?raw'
import LatencyCardSource from '@/components/dashboard/LatencyCard.vue?raw'
import RagMetricsCardSource from '@/components/dashboard/RagMetricsCard.vue?raw'
import TokenUsageCardSource from '@/components/dashboard/TokenUsageCard.vue?raw'

describe('unified workspace menus', () => {
  it('uses Reka radio menus for smart-table tag and rating filters', () => {
    expect(SmartFormsSource).toContain('<DropdownMenuRadioGroup v-model="tagFilter">')
    expect(SmartFormsSource).toContain('<DropdownMenuRadioGroup v-model="minRating">')
    expect(LibraryTagPickerSource).toContain('<DropdownMenu v-model:open="expanded">')
  })

  it('shares the pointer-positioned menu surface across context menus', () => {
    expect(mainSource).toContain("import './assets/menu-system.css'")
    expect(SmartFormsSource).toContain('table-context-menu ui-floating-menu-surface')
    expect(VaultSource).toContain('context-menu ui-floating-menu-surface')
    expect(CodeEditorSource).toContain('markdown-context-menu ui-floating-menu-surface')
  })

  it('uses Reka menus for Agent toolbar and session history actions', () => {
    expect(AgentPanelSource).toContain('<DropdownMenu v-model:open="skillMenuOpen">')
    expect(AgentPanelSource).toContain('<DropdownMenuRadioGroup v-model="agentLoopModeModel">')
    expect(SessionDrawerSource).toContain('<DropdownMenu')
    expect(SessionDrawerSource).toContain('<DropdownMenuItem')
  })

  it('reuses the shared select for queue concurrency and all dashboard selects', () => {
    expect(QueueDropdownSource).toContain('<DropdownSelect')
    expect(LatencyCardSource).toContain('<DropdownSelect')
    expect(RagMetricsCardSource).toContain('<DropdownSelect')
    expect(TokenUsageCardSource.match(/<DropdownSelect/g)).toHaveLength(3)
  })
})
