/*
 * Obs token aggregation tests.
 *
 * Usage:
 * Locks the dashboard token chart contract to model pools only. Runtime nodes
 * and concrete provider model names must never become chart series.
 */

import { describe, expect, it } from 'vitest'

import { buildRagHistory, buildRagMetrics, buildTokenSeries } from '../useObsData'

describe('buildTokenSeries', () => {
  it('aggregates token usage by large/small model pool only', () => {
    const series = buildTokenSeries([
      {
        role: 'assistant',
        created_at: '2026-07-16T15:00:00.000Z',
        trace: [
          {
            node: 'safety_input',
            event: 'passed',
            model_tier: 'runtime',
            model_name: 'safety_input',
            token_usage: { total_tokens: 1 },
          },
          {
            node: 'agent',
            event: 'model_response',
            model_tier: 'large',
            model_name: 'deepseek-v4-flash',
            token_usage: { input_tokens: 400, output_tokens: 53, total_tokens: 453 },
          },
          {
            node: 'planner',
            event: 'strategy_generated',
            model_tier: 'small',
            model_name: 'moonshot-v1-8k',
            token_usage: { total_tokens: 5 },
          },
          {
            node: 'action',
            event: 'tool_call_end',
            model_tier: 'runtime',
            model_name: 'action',
            token_usage: { total_tokens: 4 },
          },
          {
            node: 'safety_output',
            event: 'passed',
            model_tier: 'runtime',
            model_name: 'safety_output',
            token_usage: { total_tokens: 1 },
          },
        ],
      },
    ])

    expect(series).toHaveLength(1)
    expect(series[0].modelTokens).toEqual({
      '\u5927\u6a21\u578b': 453,
      '\u5c0f\u6a21\u578b': 5,
    })
    expect(Object.keys(series[0].modelTokens)).not.toContain('safety_input')
    expect(Object.keys(series[0].modelTokens)).not.toContain('safety_output')
    expect(Object.keys(series[0].modelTokens)).not.toContain('action')
    expect(Object.keys(series[0].modelTokens)).not.toContain('deepseek-v4-flash')
    expect(Object.keys(series[0].modelTokens)).not.toContain('moonshot-v1-8k')
  })

  it('drops assistant messages without model-pool token usage', () => {
    const series = buildTokenSeries([
      {
        role: 'assistant',
        trace: [
          {
            node: 'action',
            event: 'tool_call_end',
            token_usage: { total_tokens: 99 },
          },
          {
            node: 'safety_input',
            event: 'passed',
            token_usage: { total_tokens: 1 },
          },
        ],
      },
    ])

    expect(series).toEqual([])
  })
})

describe('buildRagMetrics', () => {
  it('counts search and read knowledge tools as RAG samples', () => {
    const messages = [
      {
        role: 'system',
        metadata: {
          rag_metrics: {
            recall: 50,
            hit_rate: 100,
            confidence: 80,
            memory_count: 1,
            knowledge_count: 1,
            important_count: 0,
          },
        },
      },
      {
        role: 'assistant',
        trace: [
          {
            node: 'action',
            event: 'tool_call_start',
            tool_call_id: 'search_1',
            tool_name: 'search_knowledge',
            tool_args_summary: 'query=崩铁',
          },
          {
            node: 'action',
            event: 'tool_call_end',
            tool_call_id: 'search_1',
            tool_name: 'search_knowledge',
            result_summary: '=== 内容匹配 ===\\n  [K1] 崩铁.md\\n  [K2] docs/区别.md',
          },
          {
            node: 'action',
            event: 'tool_call_end',
            tool_call_id: 'read_1',
            tool_name: 'read_knowledge_file',
            result_summary: '## 崩铁\\n完整文件内容',
          },
        ],
      },
    ]

    expect(buildRagMetrics(messages)).toEqual({
      recall: 72.2,
      hitRate: 100,
      confidence: 93.3,
      memoryCount: 1,
      knowledgeCount: 4,
      importantCount: 0,
      turnCount: 3,
    })
    expect(buildRagHistory(messages)).toEqual([
      { turn: 1, recall: 50, hitRate: 100, confidence: 80 },
      { turn: 2, recall: 58.4, hitRate: 100, confidence: 90 },
      { turn: 3, recall: 72.2, hitRate: 100, confidence: 93.3 },
    ])
  })
})
