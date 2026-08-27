<!--
  New literature dialog.

  Usage:
  LiteratureReadingView owns upload, ingestion, extraction, and persistence;
  this dialog mirrors the library form surface and previews the generated row
  through the same field blocks used by expanded literature cards.
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import LiteratureFieldBlock from '@/components/literature_reading/LiteratureFieldBlock.vue'
import type { SmartLiteratureForm, SmartRow } from '@/components/smart_forms/smartLiteratureTable'

defineProps<{
  open: boolean
  preparing: boolean
  form: SmartLiteratureForm | null
  row: SmartRow | null
  assetPath: string
}>()

const emit = defineEmits<{
  close: []
  file: [file: File]
  create: []
  addField: [event: MouseEvent]
  updateCell: [columnId: string, value: string]
}>()

const input = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)

/** Accepts one literature source from the native file picker. */
function selectFile(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('file', file)
}

/** Accepts one dragged literature source. */
function dropFile(event: DragEvent): void {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('file', file)
}

</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-backdrop" @click.self="emit('close')">
      <section class="dialog-panel library-form-surface" role="dialog" aria-modal="true" aria-label="新建文献">
        <header class="dialog-head">
          <h2>新建文献</h2>
          <button class="icon-btn" type="button" title="关闭" @click="emit('close')"><IcIcon name="close" :size="16" /></button>
        </header>
        <section class="file-zone">
          <input ref="input" class="hidden-input" type="file" @change="selectFile" />
          <button
            class="file-drop"
            :class="{ active: dragActive }"
            type="button"
            @click="input?.click()"
            @dragenter.prevent="dragActive = true"
            @dragover.prevent="dragActive = true"
            @dragleave.prevent="dragActive = false"
            @drop.prevent="dropFile"
          >
            <IcIcon name="cloud-upload" :size="24" />
            <span>{{ preparing ? '正在灌库并生成字段…' : row?.cells.literature_file?.fileName || '拖拽文献到这里' }}</span>
          </button>
        </section>
        <section v-if="row && form" class="preview-fields">
          <LiteratureFieldBlock
            v-for="column in form.columns.filter((item) => item.type !== 'index')"
            :key="column.id"
            :column="column"
            :cell="row.cells[column.id] ?? { value: '' }"
            :markdown-path="assetPath"
            @update="emit('updateCell', column.id, $event)"
          />
        </section>
        <footer class="dialog-actions">
          <button class="secondary-btn" type="button" @click="emit('addField', $event)">新增字段</button>
          <span></span>
          <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
          <button class="primary-btn" type="button" :disabled="!row || preparing" @click="emit('create')">创建</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop { position: fixed; inset: 0; z-index: 1100; display: grid; place-items: center; padding: 16px; background: rgba(0, 0, 0, 0.42); }
.dialog-panel { display: grid; width: min(860px, 100%); max-height: calc(100vh - 32px); overflow: hidden; border: 1px solid var(--color-border); border-radius: 28px; background: var(--color-surface); color: var(--color-text); }
.dialog-head,.dialog-actions { display: flex; align-items: center; gap: 8px; padding: 10px 16px; }
.dialog-head { justify-content: space-between; }.dialog-head h2 { margin: 0; font-size: calc(15px * var(--font-scale)); }
.icon-btn { width: 28px; height: 28px; padding: 0; border: 0; background: transparent; color: var(--color-text-muted); }
.file-zone { padding: 6px 16px 14px; }.hidden-input { display: none; }
.file-drop { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; min-height: 128px; padding: 16px; border: 1px dashed var(--color-border-strong); border-radius: 28px; background: var(--color-canvas); color: var(--color-text-secondary); font: inherit; }
.file-drop:hover,.file-drop.active { border-color: var(--color-primary); background: var(--color-primary-softer); color: var(--color-primary); }
.preview-fields { display: grid; gap: 10px; padding: 0 16px 16px; overflow: auto; }
.dialog-actions > span { flex: 1; }
.secondary-btn,.primary-btn { min-height: 32px; padding: 0 16px; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface-raised); color: var(--color-text); font: inherit; }
.primary-btn { border-color: var(--color-primary); background: var(--color-primary); color: #fff; }.primary-btn:disabled { opacity: .45; }
@media (max-width: 640px) { .dialog-panel { height: calc(100vh - 24px); }.dialog-actions { flex-wrap: wrap; }.dialog-actions > span { display: none; } }
</style>
