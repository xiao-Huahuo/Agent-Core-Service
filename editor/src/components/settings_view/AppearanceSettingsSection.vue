<!--
  Appearance settings section.

  Usage:
  Edits theme mode and global font stacks. The parent owns persistence.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { ThemeMode } from '@/types/settings'

const uiFontFamiliesDraft = defineModel<string[]>('uiFontFamiliesDraft', { required: true })
const textFontFamiliesDraft = defineModel<string[]>('textFontFamiliesDraft', { required: true })
const fontSizePercentDraft = defineModel<number>('fontSizePercentDraft', { required: true })
const themePrimaryColorDraft = defineModel<string>('themePrimaryColorDraft', { required: true })
const themeSoftColorDraft = defineModel<string>('themeSoftColorDraft', { required: true })

const props = defineProps<{
  themeOptions: Array<{ value: ThemeMode; label: string }>
  themeMode: ThemeMode
  availableFontFamilies: string[]
  fontsLoading: boolean
}>()

const emit = defineEmits<{
  setThemeMode: [mode: ThemeMode]
  saveFontFamilies: [payload: { target: 'ui' | 'text'; families: string[] }]
  saveFontSize: [percent: number]
  previewThemeColors: []
  saveThemeColors: []
  resetThemeColors: []
}>()

const activeFontPicker = ref<'ui' | 'text' | null>(null)
const uiFontQuery = ref('')
const textFontQuery = ref('')

function normalizeFontFamily(value: string): string {
  return value.replace(/[;{}]/g, '').trim()
}

function normalizeThemeColor(value: string): string {
  const color = value.trim()
  if (/^#[0-9a-fA-F]{6}$/u.test(color)) return color.toLowerCase()
  return ''
}

function handleThemeColorTextInput(target: 'primary' | 'soft', value: string) {
  const normalized = normalizeThemeColor(value)
  if (!normalized) return
  if (target === 'primary') {
    themePrimaryColorDraft.value = normalized
  } else {
    themeSoftColorDraft.value = normalized
  }
  emit('previewThemeColors')
}

function handleThemeColorPickerInput(target: 'primary' | 'soft', value: string) {
  if (target === 'primary') {
    themePrimaryColorDraft.value = value
  } else {
    themeSoftColorDraft.value = value
  }
  emit('previewThemeColors')
}

function activeFamilies(target: 'ui' | 'text'): string[] {
  return target === 'ui' ? uiFontFamiliesDraft.value : textFontFamiliesDraft.value
}

function activeQuery(target: 'ui' | 'text'): string {
  return target === 'ui' ? uiFontQuery.value : textFontQuery.value
}

function setActiveQuery(target: 'ui' | 'text', value: string) {
  if (target === 'ui') {
    uiFontQuery.value = value
  } else {
    textFontQuery.value = value
  }
}

function filteredFontOptions(target: 'ui' | 'text'): string[] {
  const selected = new Set(activeFamilies(target).map((item) => item.toLowerCase()))
  const query = activeQuery(target).toLowerCase()
  return props.availableFontFamilies
    .filter((family) => !selected.has(family.toLowerCase()))
    .filter((family) => !query || family.toLowerCase().includes(query))
    .slice(0, 80)
}

const uiFontOptions = computed(() => filteredFontOptions('ui'))
const textFontOptions = computed(() => filteredFontOptions('text'))

function normalizeFontSizePercent(value: number | string): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 100
  return Math.max(50, Math.min(150, Math.round(parsed)))
}

function saveFamilies(target: 'ui' | 'text', families: string[]) {
  emit('saveFontFamilies', { target, families })
}

function updateFontSize(value: number | string) {
  const normalized = normalizeFontSizePercent(value)
  fontSizePercentDraft.value = normalized
  emit('saveFontSize', normalized)
}

function saveFontSize() {
  const normalized = normalizeFontSizePercent(fontSizePercentDraft.value)
  fontSizePercentDraft.value = normalized
  emit('saveFontSize', normalized)
}

function addFontFamily(target: 'ui' | 'text', family: string) {
  const normalized = normalizeFontFamily(family)
  if (!normalized) return
  const current = activeFamilies(target)
  if (current.some((item) => item.toLowerCase() === normalized.toLowerCase())) {
    activeFontPicker.value = null
    return
  }
  saveFamilies(target, [...current, normalized])
  setActiveQuery(target, '')
  activeFontPicker.value = null
}

function removeFontFamily(target: 'ui' | 'text', family: string) {
  saveFamilies(target, activeFamilies(target).filter((item) => item !== family))
}

function handleFontInputKeydown(event: KeyboardEvent, target: 'ui' | 'text') {
  if (event.key !== 'Enter') return
  event.preventDefault()
  addFontFamily(target, activeQuery(target))
}

function handleDocumentPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('.font-family-control')) {
    activeFontPicker.value = null
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})
</script>

<template>
  <div class="setting-section">
    <h3>主题</h3>
    <div class="theme-row">
      <button
        v-for="option in themeOptions"
        :key="option.value"
        :class="['theme-'+option.value, { active: themeMode === option.value }]"
        type="button"
        @click="$emit('setThemeMode', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="color-control">
      <div class="color-control-header">
        <label>主主题色</label>
        <span>按钮、选中态和 header Agent 入口</span>
      </div>
      <div class="color-row">
        <input
          :value="themePrimaryColorDraft"
          class="color-picker"
          type="color"
          @input="handleThemeColorPickerInput('primary', ($event.target as HTMLInputElement).value)"
        />
        <input
          :value="themePrimaryColorDraft"
          class="color-text"
          spellcheck="false"
          @change="handleThemeColorTextInput('primary', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <div class="color-control">
      <div class="color-control-header">
        <label>柔和主题色</label>
        <span>浅紫背景、hover 和弱选中态</span>
      </div>
      <div class="color-row">
        <input
          :value="themeSoftColorDraft"
          class="color-picker"
          type="color"
          @input="handleThemeColorPickerInput('soft', ($event.target as HTMLInputElement).value)"
        />
        <input
          :value="themeSoftColorDraft"
          class="color-text"
          spellcheck="false"
          @change="handleThemeColorTextInput('soft', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <div class="model-actions appearance-actions">
      <button class="save-model-btn" type="button" @click="$emit('saveThemeColors')">保存主题色</button>
      <button class="cancel-model-btn" type="button" @click="$emit('resetThemeColors')">重置默认色</button>
    </div>

    <h3 style="margin-top: 20px">字体</h3>
    <div class="font-family-control font-size-control">
      <div class="font-family-header">
        <label>字体大小</label>
        <span>{{ fontSizePercentDraft }}%</span>
      </div>
      <div class="font-size-row">
        <input
          :value="fontSizePercentDraft"
          max="150"
          min="50"
          step="1"
          type="range"
          @change="saveFontSize"
          @input="updateFontSize(($event.target as HTMLInputElement).value)"
        />
        <input
          :value="fontSizePercentDraft"
          class="font-size-number"
          max="150"
          min="50"
          step="1"
          type="number"
          @blur="saveFontSize"
          @change="saveFontSize"
          @input="updateFontSize(($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <div class="font-family-control">
      <div class="font-family-header">
        <label>界面字体</label>
        <span>{{ uiFontFamiliesDraft.length ? `${uiFontFamiliesDraft.length} 个字体家族` : '使用默认字体栈' }}</span>
      </div>
      <div class="font-chip-row">
        <button
          v-for="family in uiFontFamiliesDraft"
          :key="family"
          class="font-chip"
          type="button"
          @click="removeFontFamily('ui', family)"
        >
          {{ family }} x
        </button>
        <button class="font-add-button" type="button" @click.stop="activeFontPicker = activeFontPicker === 'ui' ? null : 'ui'">
          添加字体
        </button>
      </div>
      <div v-if="activeFontPicker === 'ui'" class="font-picker-popover" @pointerdown.stop>
        <input
          v-model="uiFontQuery"
          autocomplete="off"
          placeholder="搜索或输入字体家族"
          spellcheck="false"
          @keydown="handleFontInputKeydown($event, 'ui')"
        />
        <div class="font-option-list">
          <button
            v-for="family in uiFontOptions"
            :key="family"
            type="button"
            @click="addFontFamily('ui', family)"
          >
            <span :style="{ fontFamily: family }">{{ family }}</span>
          </button>
          <button v-if="uiFontQuery.trim()" type="button" @click="addFontFamily('ui', uiFontQuery)">
            添加 "{{ uiFontQuery.trim() }}"
          </button>
          <p v-if="fontsLoading" class="font-empty">正在读取本机字体...</p>
          <p v-else-if="!uiFontOptions.length && !uiFontQuery.trim()" class="font-empty">没有可添加字体</p>
        </div>
      </div>
    </div>

    <div class="font-family-control">
      <div class="font-family-header">
        <label>文字字体</label>
        <span>{{ textFontFamiliesDraft.length ? `${textFontFamiliesDraft.length} 个字体家族` : '使用默认字体栈' }}</span>
      </div>
      <div class="font-chip-row">
        <button
          v-for="family in textFontFamiliesDraft"
          :key="family"
          class="font-chip"
          type="button"
          @click="removeFontFamily('text', family)"
        >
          {{ family }} x
        </button>
        <button class="font-add-button" type="button" @click.stop="activeFontPicker = activeFontPicker === 'text' ? null : 'text'">
          添加字体
        </button>
      </div>
      <div v-if="activeFontPicker === 'text'" class="font-picker-popover" @pointerdown.stop>
        <input
          v-model="textFontQuery"
          autocomplete="off"
          placeholder="搜索或输入字体家族"
          spellcheck="false"
          @keydown="handleFontInputKeydown($event, 'text')"
        />
        <div class="font-option-list">
          <button
            v-for="family in textFontOptions"
            :key="family"
            type="button"
            @click="addFontFamily('text', family)"
          >
            <span :style="{ fontFamily: family }">{{ family }}</span>
          </button>
          <button v-if="textFontQuery.trim()" type="button" @click="addFontFamily('text', textFontQuery)">
            添加 "{{ textFontQuery.trim() }}"
          </button>
          <p v-if="fontsLoading" class="font-empty">正在读取本机字体...</p>
          <p v-else-if="!textFontOptions.length && !textFontQuery.trim()" class="font-empty">没有可添加字体</p>
        </div>
      </div>
    </div>
    <p class="setting-hint">字体按从左到右的顺序组成 font-family;留空时使用原默认 fallback。</p>
  </div>
</template>

