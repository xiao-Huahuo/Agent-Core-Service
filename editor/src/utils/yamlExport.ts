/*
 * 简易 YAML 序列化工具。
 *
 * 用于将会话数据导出为 YAML 格式的纯文本字符串。
 * 覆盖基本类型：string、number、boolean、null、array、object。
 */

function needsQuoting(value: string): boolean {
  return /[:#{}[\],&*?|>!%@`"']/.test(value)
    || /^\s/.test(value)
    || /\s$/.test(value)
    || /^[\d.-]/.test(value)
    || value === ''
    || value === 'true'
    || value === 'false'
    || value === 'null'
    || value === 'yes'
    || value === 'no'
}

function quoteIfNeeded(value: string): string {
  if (needsQuoting(value)) {
    const escaped = value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
    return `"${escaped}"`
  }
  return value
}

function isMultiline(value: string): boolean {
  return value.includes('\n')
}

function serializeValue(value: unknown, indent: number, indentSize: number): string {
  const pad = ' '.repeat(indent)

  if (value === null || value === undefined) {
    return 'null'
  }

  if (typeof value === 'string') {
    // Insert zero-width space zero-width space at start to avoid YAML parsing as literal
    if (isMultiline(value)) {
      const lines = value.split('\n')
      // Check if last line is empty and trim it
      while (lines.length > 0 && lines[lines.length - 1] === '') {
        lines.pop()
      }
      return `|\n${lines.map((line) => `${pad}  ${line}`).join('\n')}`
    }
    return quoteIfNeeded(value)
  }

  if (typeof value === 'number') {
    return String(value)
  }

  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '[]'
    }
    const allPrimitives = value.every(
      (item) => item === null || typeof item !== 'object' || (Array.isArray(item) && item.length === 0),
    )
    if (allPrimitives) {
      return `[${value.map((item) => serializeValue(item, indent, indentSize)).join(', ')}]`
    }
    return value
      .map((item) => {
        if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
          const keys = Object.keys(item as Record<string, unknown>)
          if (keys.length === 0) return `${pad}- {}`
          const firstKey = keys[0]
          const firstVal = (item as Record<string, unknown>)[firstKey]
          const restKeys = keys.slice(1)
          const firstLine = serializeValue(firstVal, indent + indentSize + 2, indentSize)
          const header = `${pad}- ${firstKey}: ${firstLine}`
          if (restKeys.length === 0) return header
          return `${header}\n${restKeys
            .map((key) => {
              const val = (item as Record<string, unknown>)[key]
              return `${pad}${' '.repeat(indentSize)}${key}: ${serializeValue(val, indent + indentSize, indentSize)}`
            })
            .join('\n')}`
        }
        return `${pad}- ${serializeValue(item, indent + indentSize, indentSize)}`
      })
      .join('\n')
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>)
    if (keys.length === 0) return '{}'
    return keys
      .map((key) => {
        const val = (value as Record<string, unknown>)[key]
        return `${pad}${key}: ${serializeValue(val, indent + indentSize, indentSize)}`
      })
      .join('\n')
  }

  return String(value)
}

export function toYaml(value: unknown, indentSize = 2): string {
  if (typeof value !== 'object' || value === null) {
    return serializeValue(value, 0, indentSize)
  }
  return serializeValue(value, 0, indentSize)
}
