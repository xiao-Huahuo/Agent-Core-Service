<!--
  Reusable library tag picker.

  Usage:
  Binds selected tags with v-model and offers the library's existing tags in a
  smoothly expanding pill list. New text can still be committed with Enter.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import type { LibraryTag } from '@/types/knowledge'

defineOptions({ name: 'LibraryTagPicker' })

const props = defineProps<{ availableTags: LibraryTag[] }>()
const tags = defineModel<string[]>({ required: true })
const draft = ref('')
const expanded = ref(false)
const injectedTags = ref(new Set<string>())
const candidates = computed(() => props.availableTags.map((tag) => tag.name).filter((name) => !tags.value.includes(name)))
const originalTags = computed(() => tags.value.filter((tag) => !injectedTags.value.has(tag)))
const injectedTagList = computed(() => tags.value.filter((tag) => injectedTags.value.has(tag)))

function addTag(raw = draft.value, injected = false) {
  const name = raw.trim()
  if (name && !tags.value.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
    tags.value = [...tags.value, name]
    if (injected) injectedTags.value = new Set([...injectedTags.value, name])
  }
  draft.value = ''
}

function removeTag(name: string) {
  tags.value = tags.value.filter((tag) => tag !== name)
  const nextInjectedTags = new Set(injectedTags.value)
  nextInjectedTags.delete(name)
  injectedTags.value = nextInjectedTags
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ',') return
  event.preventDefault()
  addTag()
}
</script>

<template>
  <div class="library-tag-picker">
    <div class="tag-input-wrap">
      <input v-model="draft" type="text" spellcheck="false" placeholder="输入标签后回车" @focus="expanded = true" @keydown="handleKeydown" />
      <button type="button" :aria-expanded="expanded" title="选择已有标签" @click="expanded = !expanded">
        <IcIcon name="chevron-down" :size="15" />
      </button>
    </div>
    <div class="tag-options" :class="{ expanded }">
      <div class="tag-options-inner">
        <button v-for="tag in candidates" :key="tag" class="tag-pill" type="button" @click="addTag(tag, true)">{{ tag }}</button>
        <span v-if="!candidates.length" class="tag-empty">没有可添加的标签</span>
      </div>
    </div>
    <div v-if="expanded && tags.length" class="tag-divider"></div>
    <div v-if="tags.length" class="tag-list">
      <div v-if="originalTags.length" class="tag-group">
        <button v-for="tag in originalTags" :key="tag" class="tag-pill selected" type="button" :title="`移除 ${tag}`" @click="removeTag(tag)">
          <span>{{ tag }}</span><IcIcon name="cancel" :size="13" />
        </button>
      </div>
      <div v-if="originalTags.length && injectedTagList.length" class="tag-divider"></div>
      <div v-if="injectedTagList.length" class="tag-group">
        <button v-for="tag in injectedTagList" :key="tag" class="tag-pill selected" type="button" :title="`移除 ${tag}`" @click="removeTag(tag)">
          <span>{{ tag }}</span><IcIcon name="cancel" :size="13" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.library-tag-picker { display: grid; gap: 6px; }
.tag-input-wrap { display: flex; align-items: center; min-height: 36px; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-canvas); padding-left: 14px; }
.tag-input-wrap input { flex: 1; min-width: 0; height: 34px; border: 0; outline: 0; background: transparent; color: var(--color-text); font-size: calc(13px * var(--font-scale)); }
.tag-input-wrap button { display: grid; place-items: center; width: 34px; height: 34px; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-muted); cursor: pointer; transition: transform var(--transition-fast); }
.tag-input-wrap button[aria-expanded="true"] { color: var(--color-primary); transform: rotate(180deg); }
.tag-options { display: grid; grid-template-rows: 0fr; opacity: 0; transition: grid-template-rows var(--transition-normal), opacity var(--transition-fast); }
.tag-options.expanded { grid-template-rows: 1fr; opacity: 1; }
.tag-options-inner { display: flex; flex-wrap: wrap; gap: 6px; min-height: 0; overflow: hidden; padding: 0 2px; }
.tag-list { display: grid; gap: 10px; }
.tag-group { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-pill { display: inline-flex; align-items: center; gap: 5px; max-width: 160px; min-height: 24px; border: 0; border-radius: 999px; background: color-mix(in srgb, var(--color-primary) 30%, transparent); color: var(--color-primary); padding: 0 9px; font-size: calc(12px * var(--font-scale)); cursor: pointer; }
.tag-pill:nth-child(6n + 2) { background: color-mix(in srgb, var(--color-accent) 30%, transparent); color: var(--color-accent); }
.tag-pill:nth-child(6n + 3) { background: color-mix(in srgb, var(--color-success) 30%, transparent); color: var(--color-success); }
.tag-pill:nth-child(6n + 4) { background: color-mix(in srgb, var(--color-warning) 30%, transparent); color: var(--color-warning); }
.tag-pill:nth-child(6n + 5) { background: rgba(113, 70, 214, 0.30); color: #8d6eea; }
.tag-pill:nth-child(6n) { background: rgba(0, 155, 166, 0.30); color: #1ac0c8; }
.tag-pill span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-divider { height: 1px; background: var(--color-border-strong); margin: 6px 0; }
.tag-empty { color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
</style>
