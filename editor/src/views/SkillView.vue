<!--
  Skill configuration page.

  Usage:
  Shows built-in and user-level Agent skills, lets the user enable/disable
  them, create custom skills, and read the local Skill format guide.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { BookOpen, Check, FileText, FolderPlus, RefreshCw, SlidersHorizontal, X } from 'lucide-vue-next'

import { useSkillsStore } from '@/stores/skills'
import { useSettingsStore } from '@/stores/settings'

const skillsStore = useSkillsStore()
const settingsStore = useSettingsStore()
const activeTab = ref<'overview' | 'custom'>('overview')
const specOpen = ref(false)
const name = ref('')
const description = ref('')
const body = ref('')

const groupedSkills = computed(() => [
  { title: '内置 Skill', items: skillsStore.builtinSkills },
  { title: '用户 Skill', items: skillsStore.userSkills },
])

async function openSpec() {
  await skillsStore.loadSpec()
  specOpen.value = true
}

async function createCustomSkill() {
  await skillsStore.addUserSkill({
    name: name.value,
    description: description.value,
    body: body.value,
  })
  name.value = ''
  description.value = ''
  body.value = ''
  activeTab.value = 'overview'
}

onMounted(() => {
  void skillsStore.loadSkills()
})

watch(
  () => [
    settingsStore.profile.userId,
    settingsStore.profile.knowledgeDir,
    settingsStore.profile.activeLibraryId,
  ],
  () => {
    void skillsStore.loadSkills()
  },
)
</script>

<template>
  <section class="skill-page">
    <header class="skill-header">
      <div>
        <h1>Skill</h1>
        <p>{{ skillsStore.enabledCount }} / {{ skillsStore.skills.length }} enabled</p>
      </div>
      <div class="header-actions">
        <button type="button" class="icon-button" title="刷新" aria-label="刷新" @click="skillsStore.loadSkills">
          <RefreshCw :size="16" />
        </button>
        <button type="button" class="icon-button" title="规范" aria-label="规范" @click="openSpec">
          <BookOpen :size="16" />
        </button>
      </div>
    </header>

    <div class="tabs" role="tablist" aria-label="Skill views">
      <button type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
        <FileText :size="15" />
        <span>概览</span>
      </button>
      <button type="button" :class="{ active: activeTab === 'custom' }" @click="activeTab = 'custom'">
        <SlidersHorizontal :size="15" />
        <span>定制</span>
      </button>
    </div>

    <p v-if="skillsStore.error" class="error-line">{{ skillsStore.error }}</p>

    <div v-if="activeTab === 'overview'" class="overview">
      <div v-if="skillsStore.loading" class="empty-line">Loading skills...</div>
      <section v-for="group in groupedSkills" :key="group.title" class="skill-group">
        <div class="group-title">
          <h2>{{ group.title }}</h2>
          <span>{{ group.items.length }}</span>
        </div>
        <div v-if="group.items.length" class="skill-grid">
          <TransitionGroup appear name="sc" tag="div" class="skill-grid-inner">
          <article v-for="(skill, i) in group.items" :key="skill.skill_id" class="skill-card" :style="{ '--i': i }">
            <div class="card-head">
              <div>
                <h3>{{ skill.name }}</h3>
                <p>{{ skill.skill_id }}</p>
              </div>
              <label class="switch" :title="skill.enabled ? '关闭' : '启用'" @click.stop>
                <input
                  type="checkbox"
                  :checked="skill.enabled"
                  :disabled="skillsStore.saving"
                  @change="skillsStore.updateEnabled(skill.skill_id, ($event.target as HTMLInputElement).checked)"
                />
                <span class="toggle-bg"></span>
                <span class="toggle-thumb">
                  <span class="toggle-dot"></span>
                </span>
              </label>
            </div>
            <p class="description">{{ skill.description || 'No description.' }}</p>
            <div class="card-footer">
              <div class="meta-row">
                <span>{{ skill.source }}</span>
                <span v-if="skill.has_references">references</span>
                <span v-if="skill.has_scripts">scripts</span>
                <span v-if="skill.has_assets">assets</span>
              </div>
              <p class="path">{{ skill.path }}</p>
            </div>
          </article>
          </TransitionGroup>
        </div>
        <div v-else class="empty-line">No skills.</div>
      </section>
    </div>

    <form v-else class="custom-form" @submit.prevent="createCustomSkill">
      <label>
        <span>名称</span>
        <input v-model.trim="name" type="text" required placeholder="writing-helper" />
      </label>
      <label>
        <span>描述</span>
        <input v-model.trim="description" type="text" placeholder="何时应该使用这个 Skill" />
      </label>
      <label>
        <span>正文</span>
        <textarea v-model="body" rows="12" placeholder="写入 SKILL.md 的正文指令"></textarea>
      </label>
      <button type="submit" class="primary-button" :disabled="skillsStore.saving || !name.trim()">
        <FolderPlus :size="16" />
        <span>创建 Skill</span>
      </button>
    </form>

    <div v-if="specOpen" class="modal-mask" @click.self="specOpen = false">
      <section class="spec-modal" role="dialog" aria-modal="true" aria-label="Skill 规范">
        <header>
          <h2>Skill 规范</h2>
          <button type="button" class="icon-button" title="关闭" aria-label="关闭" @click="specOpen = false">
            <X :size="16" />
          </button>
        </header>
        <p>{{ skillsStore.spec }}</p>
        <div class="spec-tree">
          <Check :size="16" />
          <span>skill-name / SKILL.md / references / scripts / assets</span>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.skill-page {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-20);
  background: var(--color-bg-app);
  color: var(--color-text-primary);
}

.skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.skill-header h1,
.group-title h2,
.skill-card h3,
.spec-modal h2 {
  margin: 0;
}

.skill-header h1 {
  font-size: 24px;
}

.skill-header p,
.card-head p,
.path,
.description,
.empty-line {
  margin: var(--space-4) 0 0;
  color: var(--color-text-muted);
}

.header-actions,
.tabs,
.card-head,
.group-title,
.meta-row,
.spec-modal header,
.spec-tree {
  display: flex;
  align-items: center;
}

.header-actions {
  gap: var(--space-8);
}

.icon-button,
.tabs button,
.primary-button {
  border: 1px solid var(--color-border);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
}

.tabs {
  align-self: flex-start;
  gap: var(--space-4);
  padding: 3px;
  margin-bottom: var(--space-16);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
}

.tabs button,
.primary-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  min-height: 32px;
  padding: 0 var(--space-12);
  border-radius: var(--radius-sm);
}

.tabs button {
  border-color: transparent;
}

.tabs button.active,
.primary-button {
  background: var(--color-primary);
  color: #fff;
}

.overview,
.custom-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-20);
}

.skill-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.group-title {
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-8);
}

.group-title h2 {
  font-size: 15px;
}

.skill-grid {
  display: contents;
}

.skill-grid-inner {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-12);
}

.skill-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  min-width: 0;
  padding: var(--space-16) var(--space-20);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.10);
  transition:
    box-shadow 160ms ease,
    transform 160ms ease,
    background 160ms ease;
}

.skill-card:hover {
  background: var(--color-surface-raised);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.16);
  transform: translateY(-1px);
}

/* TransitionGroup animations */
.sc-move {
  transition: transform 400ms ease;
}

.sc-enter-active {
  animation: sc-card-in 350ms ease both;
  animation-delay: calc(var(--i, 0) * 40ms);
}

.sc-leave-active {
  transition: opacity 300ms ease;
}

.sc-leave-to {
  opacity: 0;
}

@keyframes sc-card-in {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(12px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.card-head {
  justify-content: space-between;
  gap: var(--space-6);
}

.skill-card h3 {
  font-size: 16px;
  line-height: 1.3;
  margin: 0;
}

.card-head p {
  overflow-wrap: anywhere;
  font-size: 11px;
  margin: var(--space-2) 0 0;
}

.description {
  flex: 1;
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-text-secondary);
  margin: 0;
}

.card-footer {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding-top: var(--space-10);
  border-top: 1px solid var(--color-border);
  min-height: 64px;
  justify-content: center;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.meta-row span {
  padding: 2px var(--space-8);
  border: 1px solid color-mix(in srgb, var(--color-primary) 42%, transparent);
  border-radius: 999px;
  background: var(--color-primary-softer);
  color: var(--color-primary);
  font-size: 11px;
}

.path {
  overflow-wrap: anywhere;
  font-size: 11px;
  margin: 0;
  color: var(--color-text-tertiary);
}

/* === tool-registry style toggle === */
.skill-card .switch {
  position: relative;
  width: 32px;
  height: 20px;
  flex-shrink: 0;
}

.skill-card .switch input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
}

.skill-card .switch .toggle-label {
  display: block;
  width: 100%;
  height: 100%;
  position: static;
}

.skill-card .switch .toggle-label::after {
  display: none;
}

.skill-card .switch .toggle-bg {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--color-text-muted);
  opacity: 0.3;
  transition: opacity 0.3s, background 0.3s;
  pointer-events: none;
}

.skill-card .switch .toggle-thumb {
  position: absolute;
  top: 0;
  left: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  transition: left 0.3s, background 0.3s;
  pointer-events: none;
  z-index: 1;
  margin: auto;
  bottom: 0;
}

.skill-card .switch .toggle-dot {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-surface);
  transition: transform 0.2s;
}

.skill-card .switch input:checked ~ .toggle-bg {
  opacity: 1;
  background: var(--color-primary);
}

.skill-card .switch input:checked ~ .toggle-thumb {
  left: 16px;
  background: var(--color-primary);
}

.skill-card .switch input:checked ~ .toggle-thumb .toggle-dot {
  transform: scale(0);
}

.custom-form {
  max-width: 760px;
}

.custom-form label {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  color: var(--color-text-muted);
}

.custom-form input,
.custom-form textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-10);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  font: inherit;
}

.custom-form textarea {
  resize: vertical;
  line-height: 1.5;
}

.primary-button {
  align-self: flex-start;
}

.error-line {
  color: var(--color-danger);
}

.modal-mask {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.48);
  z-index: 30;
}

.spec-modal {
  width: min(560px, calc(100vw - 32px));
  padding: var(--space-16);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
  box-shadow: var(--shadow-lg);
}

.spec-modal header {
  justify-content: space-between;
  margin-bottom: var(--space-12);
}

.spec-modal p {
  line-height: 1.55;
  color: var(--color-text-secondary);
}

.spec-tree {
  gap: var(--space-8);
  margin-top: var(--space-12);
  color: var(--color-text-muted);
}
</style>
