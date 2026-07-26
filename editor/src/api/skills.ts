/*
 * Skill management API client.
 *
 * Usage:
 * Views and stores call this module instead of hard-coding /skills endpoints.
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface SkillRecord {
  skill_id: string
  name: string
  description: string
  source: 'builtin' | 'user' | string
  path: string
  enabled: boolean
  metadata: Record<string, unknown>
  has_scripts: boolean
  has_references: boolean
  has_assets: boolean
}

export interface SkillListResponse {
  skills: SkillRecord[]
  count: number
}

export interface SkillCreateResponse {
  skill: SkillRecord
}

export interface SkillSpecResponse {
  spec: string
}

export function fetchSkills(userId: string): Promise<SkillListResponse> {
  return apiGet<SkillListResponse>(API_ROUTES.SKILLS, { user_id: userId })
}

export function setSkillEnabled(userId: string, skillId: string, enabled: boolean): Promise<{ skill_id: string; enabled: boolean }> {
  return apiPost<{ skill_id: string; enabled: boolean }>(API_ROUTES.SKILL_ENABLED(skillId), {
    user_id: userId,
    enabled,
  })
}

export function createSkill(params: {
  userId: string
  name: string
  description: string
  body: string
}): Promise<SkillCreateResponse> {
  return apiPost<SkillCreateResponse>(API_ROUTES.SKILLS, {
    user_id: params.userId,
    name: params.name,
    description: params.description,
    body: params.body,
  })
}

export function fetchSkillSpec(): Promise<SkillSpecResponse> {
  return apiGet<SkillSpecResponse>(API_ROUTES.SKILLS_SPEC)
}
