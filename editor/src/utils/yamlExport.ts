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
    if (value.every((item) => isFlowScalar(item))) {
      return `[${value.map((item) => serializeValue(item, indent, indentSize)).join(', ')}]`
    }
    return value
      .map((item) => {
        if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
          return serializeObjectAsListItem(item as Record<string, unknown>, indent, indentSize)
        }
        return `${pad}- ${serializeValue(item, indent + indentSize, indentSize)}`
      })
      .join('\n')
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>)
    if (keys.length === 0) return '{}'
    const nestedIndent = indent + indentSize
    return keys
      .map((key) => {
        const val = (value as Record<string, unknown>)[key]
        const rendered = serializeValue(val, nestedIndent, indentSize)
        if (isInlineMountable(val)) {
          return `${pad}${key}: ${rendered}`
        }
        return `${pad}${key}:\n${rendered}`
      })
      .join('\n')
  }

  return String(value)
}

/**
 * 判断标量是否可用流式 `[a, b]` 内联。
 *
 * 多行字符串与对象不能进入流式序列，须展开为逐行列表。
 */
function isFlowScalar(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return !isMultiline(value)
  if (typeof value === 'number' || typeof value === 'boolean') return true
  if (Array.isArray(value)) return value.every((item) => isFlowScalar(item))
  return false
}

/**
 * 判断值能否直接拼在 `key: ` 之后（单行挂载）。
 *
 * 对象与含对象/多行字符串的数组必须换行挂载（`key:\n` + 已缩进的子内容），
 * 否则首行会被拼到 key 同一行，产出 `key:   id: x` 这类非法映射。
 * 注意单键对象/单元素对象数组的渲染也只有一行，不能靠换行判定，须看值类型。
 * 多行字符串是块标量（`key: |`），必须保留在 key 同行，走内联分支。
 */
function isInlineMountable(value: unknown): boolean {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return Object.keys(value as Record<string, unknown>).length === 0
  }
  if (Array.isArray(value)) {
    return value.every((item) => isFlowScalar(item))
  }
  return true
}

function serializeObjectAsListItem(
  item: Record<string, unknown>,
  indent: number,
  indentSize: number,
): string {
  const pad = ' '.repeat(indent)
  const keys = Object.keys(item)
  if (keys.length === 0) return `${pad}- {}`
  // 列表项映射的 key 对齐到 `- ` 之后（indent + 2），子级再缩进一层。
  const keyPad = `${pad}${' '.repeat(indentSize)}`
  const nestedIndent = indent + indentSize + indentSize
  return keys
    .map((key, index) => {
      const val = item[key]
      const rendered = serializeValue(val, nestedIndent, indentSize)
      const prefix = index === 0 ? `${pad}- ` : keyPad
      if (isInlineMountable(val)) {
        return `${prefix}${key}: ${rendered}`
      }
      return `${prefix}${key}:\n${rendered}`
    })
    .join('\n')
}

export function toYaml(value: unknown, indentSize = 2): string {
  if (typeof value !== 'object' || value === null) {
    return serializeValue(value, 0, indentSize)
  }
  return serializeValue(value, 0, indentSize)
}
