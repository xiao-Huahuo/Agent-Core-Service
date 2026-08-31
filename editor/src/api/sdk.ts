/*
 * SDK 与运行组件管理 API。
 *
 * StorageSettingsSection 使用这些函数读取和管理 MW 固定的 DSH Windows Runtime；
 * 所有状态与进度均来自后端 DshRuntimePackageManager。
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type DshSdkState =
  | 'missing'
  | 'verifying'
  | 'extracting'
  | 'installing'
  | 'ready'
  | 'failed'
  | 'repairing'
  | 'cancelling'
  | 'uninstalling'

export interface DshSdkManagementStatus {
  key: 'deepseek_harness'
  label: string
  role: string
  version: string
  platform: string
  path: string
  size_bytes: number
  package_size_bytes: number
  file_count: number
  installed: boolean
  configured: boolean
  in_use: boolean
  status: DshSdkState
  message: string
  processed_bytes: number
  total_bytes: number
  progress: number | null
}

export function fetchDshSdkManagement(userId: string): Promise<DshSdkManagementStatus> {
  return apiGet(API_ROUTES.SETTINGS_DSH_SDK_MANAGEMENT, { user_id: userId })
}

export function installDshSdk(userId: string): Promise<DshSdkManagementStatus> {
  return apiPost(API_ROUTES.SETTINGS_DSH_SDK_INSTALL, { user_id: userId })
}

export function cancelDshSdkInstall(userId: string): Promise<DshSdkManagementStatus> {
  return apiPost(API_ROUTES.SETTINGS_DSH_SDK_INSTALL_CANCEL, { user_id: userId })
}

export function repairDshSdk(userId: string): Promise<DshSdkManagementStatus> {
  return apiPost(API_ROUTES.SETTINGS_DSH_SDK_REPAIR, { user_id: userId })
}

export function uninstallDshSdk(userId: string): Promise<DshSdkManagementStatus> {
  return apiPost(API_ROUTES.SETTINGS_DSH_SDK_UNINSTALL, { user_id: userId })
}
