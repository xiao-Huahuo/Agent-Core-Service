<!--
  Basic settings section.

  Usage:
  Edits knowledge library metadata, ingestion switches, theme mode, font stacks,
  and file index display preferences. The parent owns persistence.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { ThemeMode } from '@/types/settings'

const libraryNameDraft = defineModel<string>('libraryNameDraft', { required: true })
const knowledgeDirDraft = defineModel<string>('knowledgeDirDraft', { required: true })
const watchEnabledDraft = defineModel<boolean>('watchEnabledDraft', { required: true })
const autoIngestOnUploadDraft = defineModel<boolean>('autoIngestOnUploadDraft', { required: true })
const ocrEnabledDraft = defineModel<boolean>('ocrEnabledDraft', { required: true })
const knowledgeIgnorePatternsDraft = defineModel<string>('knowledgeIgnorePatternsDraft', { required: true })
const uiFontFamiliesDraft = defineModel<string[]>('uiFontFamiliesDraft', { required: true })
const textFontFamiliesDraft = defineModel<string[]>('textFontFamiliesDraft', { required: true })

const props = defineProps<{
  hasChanges: boolean
  saving: boolean
  saveMessage: string
  saveError: string
  themeOptions: Array<{ value: ThemeMode; label: string }>
  themeMode: ThemeMode
  showIndexColumn: boolean
  availableFontFamilies: string[]
  fontsLoading: boolean
}>()

const emit = defineEmits<{
  save: []
  setThemeMode: [mode: ThemeMode]
  saveFontFamilies: [payload: { target: 'ui' | 'text'; families: string[] }]
  setShowIndexColumn: [value: boolean]
}>()

const activeFontPicker = ref<'ui' | 'text' | null>(null)
const uiFontQuery = ref('')
const textFontQuery = ref('')

function normalizeFontFamily(value: string): string {
  return value.replace(/[;{}]/g, '').trim()
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

function saveFamilies(target: 'ui' | 'text', families: string[]) {
  emit('saveFontFamilies', { target, families })
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
    <h3>知识库</h3>
    <div class="setting-row">
      <label>库名称</label>
      <input v-model="libraryNameDraft" spellcheck="false" />
    </div>
    <div class="setting-row">
      <label>知识目录</label>
      <input v-model="knowledgeDirDraft" spellcheck="false" />
    </div>

    <h3 style="margin-top: 20px">字体</h3>
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
          {{ family }} ×
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
          {{ family }} ×
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
    <p class="setting-hint">字体按从左到右的顺序组成 font-family；留空时使用原默认 fallback。</p>

    <div class="setting-row toggle-row">
      <label>文件监听</label>
      <input v-model="watchEnabledDraft" type="checkbox" />
    </div>
    <div class="setting-row toggle-row">
      <label>自动灌库</label>
      <input v-model="autoIngestOnUploadDraft" type="checkbox" />
      <span class="hint-text">关闭时上传只进入文件树，点击 header 刷新或文件按钮才灌库</span>
    </div>
    <div class="setting-row toggle-row">
      <label>OCR</label>
      <input v-model="ocrEnabledDraft" type="checkbox" />
      <span class="hint-text">开启后需重启；重启时会检查并预热 PaddleOCR 中英文模型</span>
    </div>
    <div class="setting-row ignore-row">
      <label>屏蔽区</label>
      <textarea
        v-model="knowledgeIgnorePatternsDraft"
        spellcheck="false"
        placeholder="# gitignore-like&#10;private/&#10;*.tmp&#10;!private/keep.md"
      ></textarea>
    </div>
    <p class="setting-hint">被屏蔽的文件不会入库；已入库文件会在下次 Ingest 或单文件灌库时出库。</p>
    <div class="model-actions">
      <button class="save-model-btn" :disabled="saving || !hasChanges" @click="$emit('save')">
        {{ saving ? '保存中...' : '保存' }}
      </button>
      <span v-if="saveMessage" class="feedback">{{ saveMessage }}</span>
      <span v-if="saveError" class="feedback error">{{ saveError }}</span>
    </div>

    <h3 style="margin-top: 20px">主题</h3>
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
    <div class="setting-row toggle-row">
      <label>索引状态</label>
      <input
        :checked="showIndexColumn"
        type="checkbox"
        @change="$emit('setShowIndexColumn', ($event.target as HTMLInputElement).checked)"
      />
      <span class="hint-text">在文件树和文件资源管理器中显示入库状态</span>
    </div>
  </div>
</template>
