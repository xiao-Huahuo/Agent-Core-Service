/*
 * Skill configuration store.
 *
 * Usage:
 * Owns Skill list loading, enabled-state updates, custom Skill creation, and
 * the local copy of the authoring specification.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { createSkill, fetchSkillSpec, fetchSkills, setSkillEnabled } from '@/api/skills'
import type { SkillRecord } from '@/api/skills'
import { useSettingsStore } from '@/stores/settings'

export const useSkillsStore = defineStore('skills', () => {
  const skills = ref<SkillRecord[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const spec = ref('')

  const builtinSkills = computed(() => skills.value.filter((skill) => skill.source === 'builtin'))
  const userSkills = computed(() => skills.value.filter((skill) => skill.source === 'user'))
  const enabledCount = computed(() => skills.value.filter((skill) => skill.enabled).length)

  function userId(): string {
    return useSettingsStore().profile.userId || 'default'
  }

  async function loadSkills() {
    loading.value = true
    error.value = ''
    try {
      const result = await fetchSkills(userId())
      skills.value = result.skills
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load skills'
    } finally {
      loading.value = false
    }
  }

  async function loadSpec() {
    if (spec.value) return
    const result = await fetchSkillSpec()
    spec.value = result.spec
  }

  async function updateEnabled(skillId: string, enabled: boolean) {
    const target = skills.value.find((skill) => skill.skill_id === skillId)
    if (!target) return
    const previous = target.enabled
    target.enabled = enabled
    saving.value = true
    error.value = ''
    try {
      await setSkillEnabled(userId(), skillId, enabled)
    } catch (err) {
      target.enabled = previous
      error.value = err instanceof Error ? err.message : 'Failed to update skill'
    } finally {
      saving.value = false
    }
  }

  async function addUserSkill(params: { name: string; description: string; body: string }) {
    saving.value = true
    error.value = ''
    try {
      await createSkill({ userId: userId(), ...params })
      await loadSkills()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create skill'
      throw err
    } finally {
      saving.value = false
    }
  }

  return {
    skills,
    builtinSkills,
    userSkills,
    enabledCount,
    loading,
    saving,
    error,
    spec,
    loadSkills,
    loadSpec,
    updateEnabled,
    addUserSkill,
  }
})
