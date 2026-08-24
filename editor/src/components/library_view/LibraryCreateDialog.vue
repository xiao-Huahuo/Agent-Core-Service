<!--
  Library create dialog.

  Usage:
  Creates a virtual library book or collection. Book creation collects virtual
  metadata, an optional cover image key, and one selected source: uploaded file,
  direct text content, or a web URL.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import CompactCodeInput from '@/components/common/CompactCodeInput.vue'
import FormHeightTransition from '@/components/common/FormHeightTransition.vue'
import IcIcon from '@/components/common/IcIcon.vue'
import LibraryCoverUploader from '@/components/library_view/LibraryCoverUploader.vue'
import LibraryTagPicker from '@/components/library_view/LibraryTagPicker.vue'
import type { LibraryAsset, LibraryItem, LibraryTag } from '@/types/knowledge'

type CreateMode = 'book' | 'collection'
type BookSourceMode = 'file' | 'text' | 'script' | 'url'

const props = defineProps<{
  open: boolean
  mode: CreateMode
  userId: string
  availableTags: LibraryTag[]
}>()

const emit = defineEmits<{
  close: []
  create: [payload: {
    title: string
    description: string
    tags: string[]
    cover_mode: LibraryItem['cover_mode']
    cover_asset_id: string
    file: File | null
    source_mode: BookSourceMode
    text_content: string
    script_extension: string
    source_url: string
  }]
}>()

const title = ref('')
const description = ref('')
const tags = ref<string[]>([])
const coverAssetId = ref('')
const coverPreviewUrl = ref('')
const realFile = ref<File | null>(null)
const sourceMode = ref<BookSourceMode>('file')
const textContent = ref('')
const scriptExtension = ref('.py')
const sourceUrl = ref('')
const dragActive = ref(false)
const realFileInput = ref<HTMLInputElement | null>(null)

const isBook = computed(() => props.mode === 'book')
const heading = computed(() => (isBook.value ? '新增图书' : '新增集锦'))
const coverMode = computed<LibraryItem['cover_mode']>(() => (coverAssetId.value ? 'image' : 'title'))

watch(
  () => props.open,
  (open) => {
    if (!open) return
    title.value = ''
    description.value = ''
    tags.value = []
    coverAssetId.value = ''
    coverPreviewUrl.value = ''
    realFile.value = null
    sourceMode.value = 'file'
    textContent.value = ''
    scriptExtension.value = '.py'
    sourceUrl.value = ''
    dragActive.value = false
  },
)

/** Select one visible input mode without changing the persisted text contract. */
function setSourceMode(mode: BookSourceMode) {
  sourceMode.value = mode
  dragActive.value = false
}

function selectRealFile(event: Event) {
  const input = event.target as HTMLInputElement
  realFile.value = input.files?.[0] ?? null
}

function dropRealFile(event: DragEvent) {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    realFile.value = file
  }
}

/** Apply the shared uploader result to the pending library item. */
function handleCoverUploaded(asset: LibraryAsset) {
  coverAssetId.value = asset.asset_id
  coverPreviewUrl.value = asset.url
}

function submit() {
  emit('create', {
    title: title.value.trim(),
    description: description.value.trim(),
    tags: tags.value,
    cover_mode: coverMode.value,
    cover_asset_id: coverAssetId.value,
    file: realFile.value,
    source_mode: sourceMode.value,
    text_content: textContent.value,
    script_extension: scriptExtension.value.trim(),
    source_url: sourceUrl.value.trim(),
  })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-backdrop" @click.self="emit('close')">
    <section class="dialog-panel library-form-surface" role="dialog" aria-modal="true">
        <header class="dialog-head">
          <h2>{{ heading }}</h2>
          <button class="icon-btn" type="button" title="关闭" @click="emit('close')">
            <IcIcon name="close" :size="16" />
          </button>
        </header>

        <section class="upper-grid">
          <div class="cover-zone">
            <LibraryCoverUploader
              :user-id="userId"
              :preview-url="coverPreviewUrl"
              @uploaded="handleCoverUploaded"
            />
          </div>

          <div class="metadata-zone">
            <label class="field">
              <span>标题</span>
              <input class="library-input form-input-surface" v-model="title" type="text" spellcheck="false" placeholder="留空使用默认名称" />
            </label>
            <label class="field">
              <span>描述</span>
              <textarea class="library-input form-input-surface" v-model="description" rows="5" placeholder="用于搜索和归纳说明" />
            </label>
            <div class="field">
              <span>标签</span>
              <LibraryTagPicker v-model="tags" :available-tags="availableTags.map((tag) => tag.name)" />
            </div>
          </div>
        </section>

        <FormHeightTransition :watch-key="sourceMode">
          <section v-if="isBook && sourceMode === 'file'" class="file-zone">
            <input ref="realFileInput" class="hidden-input" type="file" @change="selectRealFile" />
            <button
              class="file-drop"
              :class="{ active: dragActive }"
              type="button"
              @click="realFileInput?.click()"
              @dragenter.prevent="dragActive = true"
              @dragover.prevent="dragActive = true"
              @dragleave.prevent="dragActive = false"
              @drop.prevent="dropRealFile"
            >
              <IcIcon name="cloud-upload" :size="24" />
              <span>{{ realFile?.name || '拖拽真实文件到这里' }}</span>
            </button>
          </section>

          <section v-else-if="isBook && sourceMode === 'text'" class="text-zone">
            <label class="text-content-field">
              <span>文本内容</span>
            <textarea class="library-input-surface form-input-surface" v-model="textContent" rows="8" spellcheck="false" placeholder="输入后会保存为 Markdown 文件" />
            </label>
          </section>

          <section v-else-if="isBook && sourceMode === 'script'" class="script-zone">
            <CompactCodeInput
              v-model="textContent"
              class="library-script-input form-input-surface"
              label="脚本内容"
              placeholder="输入脚本代码"
            />
            <label class="script-extension-field">
              <span>代码文件后缀</span>
              <input class="library-input-surface form-input-surface" v-model="scriptExtension" type="text" spellcheck="false" placeholder=".py" aria-label="代码文件后缀" />
            </label>
          </section>

          <section v-else-if="isBook && sourceMode === 'url'" class="url-zone">
            <label class="url-input-wrap library-input-surface form-input-surface">
              <IcIcon name="language" :size="15" />
              <input v-model="sourceUrl" type="url" spellcheck="false" placeholder="URL" />
            </label>
          </section>
        </FormHeightTransition>

        <footer class="dialog-actions" :class="{ 'collection-actions': !isBook }">
          <div v-if="isBook" class="source-mode-actions" aria-label="文件来源">
            <button
              class="source-mode-btn"
              :class="{ active: sourceMode === 'text' }"
              type="button"
              title="文本"
              aria-label="文本"
              @click="setSourceMode(sourceMode === 'text' ? 'file' : 'text')"
            >
              <IcIcon name="document" :size="16" />
            </button>
            <button
              class="source-mode-btn"
              :class="{ active: sourceMode === 'script' }"
              type="button"
              title="脚本"
              aria-label="脚本"
              @click="setSourceMode(sourceMode === 'script' ? 'file' : 'script')"
            >
              <IcIcon name="code" :size="16" />
            </button>
            <button
              class="source-mode-btn"
              :class="{ active: sourceMode === 'url' }"
              type="button"
              title="网页"
              aria-label="网页"
              @click="setSourceMode(sourceMode === 'url' ? 'file' : 'url')"
            >
              <IcIcon name="language" :size="16" />
            </button>
          </div>
          <div class="submit-actions">
            <button class="secondary-btn" type="button" @click="emit('close')">取消</button>
            <button class="primary-btn" type="button" @click="submit">
              <IcIcon name="save" :size="14" />
              创建
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.42);
}

.dialog-panel {
  width: min(760px, calc(100vw - 32px));
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 7px 16px;
}

.dialog-head h2 {
  margin: 0;
  font-size: calc(15px * var(--font-scale));
}

.upper-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 5fr);
  gap: 14px;
  padding: 16px 16px 0;
}

.metadata-zone {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
}

.field {
  display: grid;
  min-width: 0;
  gap: 7px;
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text-secondary);
}

.library-input,
.metadata-zone .field :deep(.tag-input-wrap) {
  width: 100%;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-surface) 94%, var(--color-text) 6%);
  color: var(--color-text);
  transition: box-shadow var(--transition-fast);
}

.library-input {
  outline: none;
  font-size: calc(13px * var(--font-scale));
}

.library-input[type="text"] {
  height: 36px;
  padding: 0 14px;
}

.library-input:focus,
.metadata-zone .field :deep(.tag-input-wrap:focus-within) {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-border-strong) 50%, transparent);
}

.library-input-surface,
.library-script-input {
  border: 0;
  background: color-mix(in srgb, var(--color-surface) 94%, var(--color-text) 6%);
  transition: box-shadow var(--transition-fast);
}

.library-input-surface:focus,
.library-input-surface:focus-within,
.library-script-input:focus-within {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-border-strong) 50%, transparent);
}

.library-input:is(textarea) {
  width: 100%;
  border-radius: 28px;
  padding: 10px 14px;
  resize: vertical;
}

.cover-zone {
  display: flex;
  min-width: 0;
}

.file-zone {
  padding: 14px 16px 0;
}

.text-zone,
.script-zone,
.url-zone {
  padding: 14px 16px 0;
}

.library-script-input {
  min-height: 198px;
  overflow: hidden;
  border-radius: 28px;
}

.script-extension-field {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.script-extension-field input {
  width: 96px;
  height: 30px;
  border-radius: 999px;
  outline: 0;
  color: var(--color-text);
  padding: 0 10px;
  font-family: var(--font-text);
  font-size: calc(12px * var(--font-scale));
}

.text-content-field {
  display: grid;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.text-content-field textarea {
  width: 100%;
  min-height: 168px;
  border-radius: 28px;
  color: var(--color-text);
  padding: 10px 14px;
  resize: vertical;
  outline: none;
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
}

.url-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  border-radius: 999px;
  color: var(--color-text-secondary);
  padding: 0 14px;
}

.url-input-wrap:focus-within {
  color: var(--color-primary);
}

.url-input-wrap input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.file-drop {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-height: 168px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 28px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 16px;
  cursor: pointer;
  font-size: calc(13px * var(--font-scale));
}

.file-drop:hover,
.file-drop.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.hidden-input {
  display: none;
}

.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px;
}

.source-mode-actions,
.submit-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.dialog-actions.collection-actions {
  justify-content: flex-end;
}

.source-mode-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast),
    transform 160ms ease;
}

.source-mode-btn:hover,
.source-mode-btn.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.source-mode-btn:active {
  transform: translateY(1px);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
}

.icon-btn:hover {
  background: color-mix(in srgb, var(--color-text-secondary) 10%, transparent);
  color: var(--color-text);
}

.secondary-btn,
.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 0 16px;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.primary-btn {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

@media (max-width: 720px) {
  .upper-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .dialog-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .source-mode-actions,
  .submit-actions {
    justify-content: flex-end;
  }
}
</style>
