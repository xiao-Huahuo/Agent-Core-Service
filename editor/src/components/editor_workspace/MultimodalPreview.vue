<!--
  Multimodal file preview surface.

  Usage:
  Renders backend preview payloads for images, PDFs, tables, DOCX-derived HTML,
  and unsupported binary files in the editor center pane.
-->
<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'

import { buildApiUrl } from '@/api/client'
import type { FilePreviewPayload } from '@/types/knowledge'

const props = defineProps<{
  preview: FilePreviewPayload | null
}>()

const safeHtml = computed(() => DOMPurify.sanitize(props.preview?.html ?? ''))

const previewSource = computed(() => {
  if (!props.preview) {
    return ''
  }
  if (props.preview.raw_url) {
    return buildApiUrl(props.preview.raw_url)
  }
  return props.preview.data_url ?? ''
})

function maxColumns(rows: string[][]): number {
  return rows.reduce((max, row) => Math.max(max, row.length), 0)
}
</script>

<template>
  <article class="multimodal-preview">
    <div v-if="!preview" class="preview-message">没有可用预览。</div>

    <img
      v-else-if="preview.kind === 'image'"
      class="image-preview"
      :src="preview.data_url"
      :alt="preview.path"
    />

    <iframe
      v-else-if="preview.kind === 'pdf'"
      class="pdf-preview"
      :src="previewSource"
      title="PDF preview"
    ></iframe>

    <div v-else-if="preview.kind === 'table'" class="table-preview">
      <section v-for="sheet in preview.sheets ?? []" :key="sheet.name" class="table-sheet">
        <h3>{{ sheet.name }}</h3>
        <div class="table-scroll">
          <table>
            <tbody>
              <tr v-for="(row, rowIndex) in sheet.rows" :key="rowIndex">
                <td v-for="columnIndex in maxColumns(sheet.rows)" :key="columnIndex">
                  {{ row[columnIndex - 1] ?? '' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-else-if="preview.kind === 'document'" class="document-preview" v-html="safeHtml"></div>

    <pre v-else-if="preview.kind === 'text'" class="text-preview">{{ preview.content }}</pre>

    <div v-else class="preview-message">
      {{ preview.message || '当前文件类型暂不支持预览。' }}
    </div>
  </article>
</template>

<style scoped>
.multimodal-preview {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  font-family: var(--font-ui);
}

.image-preview {
  max-width: 100%;
  max-height: 100%;
  margin: auto;
  object-fit: contain;
}

.pdf-preview {
  flex: 1;
  min-width: 0;
  min-height: 0;
  border: 0;
}

.table-preview,
.document-preview,
.text-preview,
.preview-message {
  flex: 1;
  min-width: 0;
  padding: var(--space-16);
}

.table-sheet + .table-sheet {
  margin-top: var(--space-16);
}

.table-sheet h3 {
  margin: 0 0 var(--space-8);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: 13px;
}

.table-scroll {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.table-scroll table {
  min-width: 100%;
  border-collapse: collapse;
  color: var(--color-text);
  font-family: var(--font-text);
  font-size: 12px;
}

.table-scroll td {
  padding: var(--space-6) var(--space-8);
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  white-space: pre-wrap;
}

.document-preview {
  max-width: 880px;
  margin: 0 auto;
  color: var(--color-text);
  font-family: var(--font-text);
  line-height: 1.7;
}

.document-preview :deep(p) {
  margin: 0 0 var(--space-10);
}

.text-preview {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-text);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.preview-message {
  display: grid;
  place-items: center;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 13px;
}
</style>
