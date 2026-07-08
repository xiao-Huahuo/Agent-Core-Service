/*
 * HTTP 客户端与 SSE 流解析器。
 *
 * 功能说明:
 * 提供 fetch 封装、user_id 管理、SSE (text/event-stream) 流式解析和通用错误类型。
 * 所有 API 请求统一通过本模块发起,不在各业务模块中直接使用 fetch。
 *
 * 使用说明:
 * import { apiGet, apiPost, streamLines, getUserId, setUserId } from '@/api/client'
 */

const USER_ID_KEY = 'agent_console_user_id'

/* ==================================================================
 * user_id 管理
 * ================================================================== */

/**
 * 从 localStorage 读取持久化的 user_id。
 * 返回空字符串表示尚未设置。
 */
export function getUserId() {
  return localStorage.getItem(USER_ID_KEY) || ''
}

/**
 * 将 user_id 写入 localStorage。
 */
export function setUserId(id) {
  localStorage.setItem(USER_ID_KEY, id)
}

/* ==================================================================
 * 错误类型
 * ================================================================== */

/**
 * API 请求错误,携带 HTTP 状态码和服务端错误信息。
 */
export class ApiError extends Error {
  /**
   * @param {number} status HTTP 状态码
   * @param {string} message 错误描述
   */
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/* ==================================================================
 * 基础请求
 * ================================================================== */

/**
 * 发起 GET 请求并返回解析后的 JSON。
 *
 * @param {string} path 请求路径,如 /sessions
 * @param {Record<string, string|number>} [params] 查询参数
 * @returns {Promise<any>} 解析后的 JSON 响应体
 */
export async function apiGet(path, params = {}, { signal } = {}) {
  const url = new URL(path, window.location.origin)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }
  const response = await fetch(url.toString(), { signal })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, text || response.statusText)
  }
  return response.json()
}

/**
 * 发起 POST 请求并返回解析后的 JSON。
 *
 * @param {string} path 请求路径
 * @param {Record<string, any>} [body] JSON 请求体
 * @returns {Promise<any>} 解析后的 JSON 响应体
 */
export async function apiPost(path, body = {}) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, text || response.statusText)
  }
  return response.json()
}

/**
 * 发起 DELETE 请求并返回解析后的 JSON。
 *
 * @param {string} path 请求路径
 * @param {Record<string, string|number>} [params] 查询参数
 * @returns {Promise<any>} 解析后的 JSON 响应体
 */
export async function apiDelete(path, params = {}) {
  const url = new URL(path, window.location.origin)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }
  const response = await fetch(url.toString(), { method: 'DELETE' })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, text || response.statusText)
  }
  return response.json()
}

/**
 * 发起 PUT 请求并返回解析后的 JSON。
 *
 * @param {string} path 请求路径
 * @param {Record<string, any>} [body] JSON 请求体
 * @returns {Promise<any>} 解析后的 JSON 响应体
 */
export async function apiPut(path, body = {}) {
  const response = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, text || response.statusText)
  }
  return response.json()
}

/* ==================================================================
 * SSE 流式解析
 * ================================================================== */

/**
 * 从 SSE 端点读取流式数据,返回 AsyncGenerator。
 *
 * 解析 text/event-stream 格式的行,每遇到 "data: <json>\n\n" 就 yield 一个 JS 对象。
 * 遇到 "data: [DONE]\n\n" 时结束迭代。
 * 使用 ReadableStream 读取,不依赖 EventSource API,以支持 POST 和自定义 header。
 *
 * @param {string} url 完整的 SSE 端点 URL
 * @returns {AsyncGenerator<Record<string, any>>} 每次 yield 一个解析后的事件对象
 */
export async function* streamLines(url, { signal } = {}) {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    throw new ApiError(response.status, 'SSE stream connection failed')
  }
  if (!response.body) {
    throw new ApiError(0, 'SSE response body is null (streaming not supported)')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  /* signal 触发时取消 reader,让 reader.read() 立即返回 {done: true} */
  if (signal) {
    if (signal.aborted) {
      reader.cancel()
    } else {
      signal.addEventListener('abort', () => reader.cancel(), { once: true })
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const trimmed = part.trim()
        if (!trimmed) continue

        for (const line of trimmed.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)

          if (payload === '[DONE]') return
          try {
            yield JSON.parse(payload)
          } catch {
            /* 跳过无法解析的 JSON 行 */
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') return
    throw err
  } finally {
    reader.releaseLock()
  }
}
