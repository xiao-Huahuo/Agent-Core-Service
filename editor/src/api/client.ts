/*
 * HTTP client helper for planned editor API calls.
 *
 * Usage:
 * Stores should import apiGet/apiPost/apiPut/apiPatch/apiDelete once the
 * backend endpoints are connected. The current mock UI does not call them yet.
 */

type QueryValue = string | number | boolean | undefined | null

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getApiOrigin(): string {
  if (import.meta.env.VITE_AGENT_API_BASE) {
    return import.meta.env.VITE_AGENT_API_BASE
  }
  if (window.location.protocol === 'file:') {
    return 'http://127.0.0.1:8002'
  }
  return window.location.origin
}

export function buildApiUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(path, getApiOrigin())
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value))
    }
  })
  return url.origin === window.location.origin ? `${url.pathname}${url.search}` : url.toString()
}

const REQUEST_TIMEOUT = 30_000

export type ApiRequestInit = RequestInit & {
  timeoutMs?: number
}

async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), init?.timeoutMs ?? REQUEST_TIMEOUT)
  const isFormData = init?.body instanceof FormData
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {}
  try {
    const response = await fetch(path, {
      headers: isFormData
        ? fetchInit.headers
        : {
            'Content-Type': 'application/json',
            ...fetchInit.headers,
          },
      signal: controller.signal,
      ...fetchInit,
    })
    if (!response.ok) {
      const detail = await readErrorDetail(response)
      throw new ApiError(response.status, `Request failed: ${response.status} ${detail || response.statusText}`)
    }
    return response.json() as Promise<T>
  } finally {
    clearTimeout(timeoutId)
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => JSON.stringify(item)).join('; ')
    }
  } catch {
    return ''
  }
  return ''
}

export function apiGet<T>(
  path: string,
  query?: Record<string, QueryValue>,
  init?: ApiRequestInit,
): Promise<T> {
  return request<T>(buildApiUrl(path, query), init)
}

export function apiPost<T>(path: string, body?: unknown, init?: ApiRequestInit): Promise<T> {
  return request<T>(buildApiUrl(path), {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
    ...init,
  })
}

export function apiPut<T>(path: string, body?: unknown, init?: ApiRequestInit): Promise<T> {
  return request<T>(buildApiUrl(path), {
    method: 'PUT',
    body: JSON.stringify(body ?? {}),
    ...init,
  })
}

export function apiPatch<T>(path: string, body?: unknown, init?: ApiRequestInit): Promise<T> {
  return request<T>(buildApiUrl(path), {
    method: 'PATCH',
    body: JSON.stringify(body ?? {}),
    ...init,
  })
}

export function apiDelete<T>(path: string, query?: Record<string, QueryValue>, init?: ApiRequestInit): Promise<T> {
  return request<T>(buildApiUrl(path, query), {
    method: 'DELETE',
    ...init,
  })
}

export function apiPostForm<T>(path: string, body: FormData, init?: ApiRequestInit): Promise<T> {
  return request<T>(buildApiUrl(path), {
    method: 'POST',
    headers: {},
    body,
    ...init,
  })
}

export async function* streamLines(
  path: string,
  options: RequestInit = {},
): AsyncGenerator<Record<string, unknown>> {
  const response = await fetch(path, options)
  if (!response.ok) {
    throw new ApiError(response.status, 'SSE stream connection failed')
  }
  if (!response.body) {
    throw new ApiError(0, 'SSE response body is null')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const signal = options.signal
  if (signal) {
    if (signal.aborted) {
      await reader.cancel()
    } else {
      signal.addEventListener('abort', () => void reader.cancel(), { once: true })
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const trimmed = part.trim()
        if (!trimmed) {
          continue
        }
        for (const line of trimmed.split('\n')) {
          if (!line.startsWith('data: ')) {
            continue
          }
          const payload = line.slice(6)
          if (payload === '[DONE]') {
            return
          }
          try {
            yield JSON.parse(payload) as Record<string, unknown>
          } catch {
            // Ignore malformed stream chunks and continue reading.
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return
    }
    throw error
  } finally {
    reader.releaseLock()
  }
}
