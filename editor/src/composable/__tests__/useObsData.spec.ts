/*
 * Obs token aggregation tests.
 *
 * Usage:
 * Locks the dashboard token chart contract to model pools only. Runtime nodes
 * and concrete provider model names must never become chart series.
 */

import { describe, expect, it } from 'vitest'

import { buildLatencyTurns, buildRagHistory, buildRagMetrics, buildTokenSeries } from '../useObsData'

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
    expect(series[0]?.modelTokens).toEqual({
      '\u5927\u6a21\u578b': 453,
      '\u5c0f\u6a21\u578b': 5,
    })
    expect(Object.keys(series[0]?.modelTokens || {})).not.toContain('safety_input')
    expect(Object.keys(series[0]?.modelTokens || {})).not.toContain('safety_output')
    expect(Object.keys(series[0]?.modelTokens || {})).not.toContain('action')
    expect(Object.keys(series[0]?.modelTokens || {})).not.toContain('deepseek-v4-flash')
    expect(Object.keys(series[0]?.modelTokens || {})).not.toContain('moonshot-v1-8k')
  })
})

describe('buildRagMetrics', () => {
  it('uses cumulative session metrics instead of the latest system message only', () => {
    const messages = [
      {
        role: 'system',
        metadata: {
          rag_metrics: {
            fill_rate: 50,
            avg_relevance: 80,
            confidence: 70,
            memory_count: 1,
            knowledge_count: 2,
            important_count: 1,
          },
        },
      },
      {
        role: 'system',
        metadata: {
          rag_metrics: {
            fill_rate: 100,
            avg_relevance: 60,
            confidence: 90,
            memory_count: 3,
            knowledge_count: 4,
            important_count: 2,
          },
        },
      },
    ]

    expect(buildRagMetrics(messages)).toEqual({
      fillRate: 75,
      avgRelevance: 70,
      confidence: 80,
      memoryCount: 4,
      knowledgeCount: 6,
      importantCount: 3,
      turnCount: 2,
    })
    expect(buildRagHistory(messages)).toEqual([
      { turn: 1, fillRate: 50, avgRelevance: 80, confidence: 70 },
      { turn: 2, fillRate: 75, avgRelevance: 70, confidence: 80 },
    ])
  })

  it('includes knowledge retrieval tool calls in cumulative RAG metrics', () => {
    const messages = [
      {
        role: 'system',
        metadata: {
          rag_metrics: {
            fill_rate: 50,
            avg_relevance: 80,
            confidence: 70,
            memory_count: 1,
            knowledge_count: 2,
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
            tool_call_id: 'call_1',
            tool_name: 'get_knowledge_context',
            tool_args_summary: 'query=test, top_k=4',
          },
          {
            node: 'action',
            event: 'tool_call_end',
            tool_call_id: 'call_1',
            tool_name: 'get_knowledge_context',
            result_count: 2,
            raw_content: '1. [K1] source\\n2. [K2] source',
          },
        ],
      },
    ]

    expect(buildRagMetrics(messages)).toEqual({
      fillRate: 50,
      avgRelevance: 40,
      confidence: 85,
      memoryCount: 1,
      knowledgeCount: 4,
      importantCount: 0,
      turnCount: 2,
    })
    expect(buildRagHistory(messages)).toEqual([
      { turn: 1, fillRate: 50, avgRelevance: 80, confidence: 70 },
      { turn: 2, fillRate: 50, avgRelevance: 40, confidence: 85 },
    ])
  })

  it('counts search and read knowledge tools as RAG samples', () => {
    const messages = [
      {
        role: 'system',
        metadata: {
          rag_metrics: {
            fill_rate: 50,
            avg_relevance: 100,
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
            raw_content: '=== 内容匹配 ===\\n  [K1] 崩铁.md\\n  [K2] docs/区别.md',
          },
          {
            node: 'action',
            event: 'tool_call_end',
            tool_call_id: 'read_1',
            tool_name: 'read_knowledge_file',
            raw_content: '## 崩铁\\n完整文件内容',
          },
        ],
      },
    ]

    expect(buildRagMetrics(messages)).toEqual({
      fillRate: 72.2,
      avgRelevance: 33.3,
      confidence: 93.3,
      memoryCount: 1,
      knowledgeCount: 4,
      importantCount: 0,
      turnCount: 3,
    })
    expect(buildRagHistory(messages)).toEqual([
      { turn: 1, fillRate: 50, avgRelevance: 100, confidence: 80 },
      { turn: 2, fillRate: 58.4, avgRelevance: 50, confidence: 90 },
      { turn: 3, fillRate: 72.2, avgRelevance: 33.3, confidence: 93.3 },
    ])
  })
})

describe('buildLatencyTurns', () => {
  it('accumulates node duration breakdown through the selected turn', () => {
    const turns = buildLatencyTurns([
      { role: 'user', content: 'first', created_at: '2026-07-16T10:00:00.000Z' },
      {
        role: 'assistant',
        content: 'first answer',
        created_at: '2026-07-16T10:00:01.000Z',
        trace: [
          { node: 'safety_input', duration_ms: 20 },
          { node: 'agent', duration_ms: 80 },
        ],
      },
      { role: 'user', content: 'second', created_at: '2026-07-16T10:00:02.000Z' },
      {
        role: 'assistant',
        content: 'second answer',
        created_at: '2026-07-16T10:00:03.000Z',
        trace: [
          { node: 'planner', duration_ms: 50 },
          { node: 'agent', duration_ms: 50 },
        ],
      },
    ])

    expect(turns).toHaveLength(2)
    expect(turns[1]?.cumulativeSeconds).toBe(0.2)
    expect(Object.fromEntries((turns[1]?.nodeBreakdown || []).map((item) => [item.node, item.durationMs]))).toEqual({
      safety_input: 20,
      agent: 130,
      planner: 50,
    })
  })
})
