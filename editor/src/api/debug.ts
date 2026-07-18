/*
 * Runtime debug API client.
 *
 * Usage:
 * Debug pages call these endpoints to render backend-reported runtime state
 * without duplicating service addresses in front-end components.
 */

import { apiGet } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type RuntimeApiKind = 'rest' | 'grpc'
export type RuntimeApiStatus = 'running' | 'stopped' | 'unknown'

export interface RuntimeApiInfo {
  kind: RuntimeApiKind
  name: string
  protocol: string
  service: string
  method: string
  path: string
  operation_id?: string
  tags?: string[]
  request: string
  response: string
  base_url: string
  summary: string
  description?: string
  status: RuntimeApiStatus
  parameters?: RuntimeRestParameter[]
  request_body?: RuntimeRestRequestBody
  responses?: Record<string, RuntimeRestResponse>
  request_schema_tree?: RuntimeSchemaNode | null
  response_schema_tree?: RuntimeSchemaNode[]
  call?: Record<string, string>
  client_streaming?: boolean
  server_streaming?: boolean
  input_type?: string
  output_type?: string
  input_fields?: RuntimeGrpcField[]
  output_fields?: RuntimeGrpcField[]
  input_schema_tree?: RuntimeSchemaNode
  output_schema_tree?: RuntimeSchemaNode
}

export interface RuntimeRestParameter {
  name: string
  in: string
  required?: boolean
  description?: string
  schema?: Record<string, unknown>
  schema_tree?: RuntimeSchemaNode | null
}

export interface RuntimeRestRequestBody {
  required?: boolean
  content?: Record<string, { schema?: Record<string, unknown>; schema_tree?: RuntimeSchemaNode | null }>
}

export interface RuntimeRestResponse {
  description?: string
  content?: Record<string, { schema?: Record<string, unknown>; schema_tree?: RuntimeSchemaNode | null }>
}

export interface RuntimeGrpcField {
  name: string
  number: number
  type: string
  label: string
  repeated: boolean
  message_type: string
}

export interface RuntimeSchemaNode {
  name: string
  type: string
  required: boolean
  description: string
  default?: unknown
  enum?: unknown[]
  number?: number | string
  label?: string
  children?: RuntimeSchemaNode[]
}

export interface RuntimeApiGroup {
  kind: RuntimeApiKind
  name: string
  base_url: string
}

export interface RuntimeApisResponse {
  api_count: number
  apis: RuntimeApiInfo[]
  groups: RuntimeApiGroup[]
}

export async function fetchRuntimeApis(): Promise<RuntimeApisResponse> {
  try {
    return await apiGet<RuntimeApisResponse>(API_ROUTES.DEBUG_RUNTIME_APIS)
  } catch (error) {
    if (error instanceof SyntaxError) {
      return fetchRuntimeApisFromBackendOrigin()
    }
    throw error
  }
}

async function fetchRuntimeApisFromBackendOrigin(): Promise<RuntimeApisResponse> {
  const response = await fetch(`http://127.0.0.1:8002${API_ROUTES.DEBUG_RUNTIME_APIS}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<RuntimeApisResponse>
}
