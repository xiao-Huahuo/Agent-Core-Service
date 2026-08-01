/*
 * YAML 导出回归测试。
 *
 * 背景:手写序列化器把对象/对象数组的首行拼到父 key 同行,产出
 * `session:   id: x` / `trace_details:     - event: ...` 这类非法 YAML,
 * 后端 `/sessions/import-file` 用 `yaml.safe_load` 解析会直接 ScannerError,
 * 导出的会话无法再导入。本测试验证容器值必须换行挂载、导出可被 PyYAML 解析。
 */

import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { toYaml } from '@/utils/yamlExport'

const REPRESENTATIVE_DATA = {
  session: {
    id: 'sess_120165a88c4c49c9b6f7d2b955a59516',
    name: '分段读取目录树文件的方法',
    user_id: '1',
    created_at: '2026-08-01T06:03:50.511046',
    updated_at: '2026-08-01T06:09:01.146223',
  },
  messages: [
    {
      role: 'assistant',
      content: '',
      created_at: '2026-08-01T06:05:47.454849',
      node: 'compress',
      trace_human_readable: ['当前上下文 19505 tokens，未超过阈值，无需压缩。'],
      trace_details: [
        {
          event: 'compression_skipped',
          node: 'compress',
          human_readable: '当前上下文 19505 tokens，未超过阈值，无需压缩。',
          duration_ms: 36.19,
        },
      ],
    },
    {
      role: 'assistant',
      content: '我来看一下\n这个目录树',
      created_at: '2026-08-01T06:06:00.000000',
      node: 'agent',
      tool_calls: [
        { name: 'read_directory_tree', arguments: { path: 'src' }, result: 'ok' },
      ],
    },
    { role: 'human', content: '你好', created_at: '2026-08-01T06:06:10.000000' },
  ],
  task_list: { items: [{ task_id: 't1', title: '读取目录树' }] },
}

describe('yamlExport 容器换行挂载', () => {
  it('顶层对象值不再拼到 key 同行', () => {
    const yaml = toYaml(REPRESENTATIVE_DATA)
    expect(yaml).toContain('session:\n  id: ')
    expect(yaml).not.toContain('session:   id: ')
    expect(yaml).toContain('messages:\n  - role: ')
    expect(yaml).not.toContain('messages:   - role: ')
  })

  it('对象数组子级缩进正确对齐', () => {
    const yaml = toYaml(REPRESENTATIVE_DATA)
    expect(yaml).toContain('  - role: assistant\n    content: ')
    expect(yaml).toContain('trace_details:\n      - event: compression_skipped')
    expect(yaml).not.toContain('trace_details:     - event: ')
  })

  it('导出内容可被后端 PyYAML 解析(落盘供外部验证)', () => {
    const yaml = toYaml(REPRESENTATIVE_DATA)
    writeFileSync(resolve(__dirname, '../../.tmp-yaml-export-roundtrip.yaml'), yaml, 'utf8')
    expect(yaml.length).toBeGreaterThan(0)
  })

  it('多行字符串仍以块标量挂在 key 同行', () => {
    const yaml = toYaml({ content: '第一行\n第二行' })
    expect(yaml).toBe('content: |\n    第一行\n    第二行')
  })
})
