<!--
  Scanner idle and running main surface.

  Provides unrestricted file selection, drag/drop, URL entry, task-local OCR
  settings, real bundled examples, and the shared pixel progress presentation.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import PixelLoader from '@/components/common/PixelLoader.vue'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useSettingsStore } from '@/stores/settings'
import type { ScannerRecord } from '@/api/scanner'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'

const props = defineProps<{ running: ScannerRecord | null }>()
const emit = defineEmits<{
  upload: [file: File, sourceKind?: string]
  crawl: [url: string]
}>()

const settingsStore = useSettingsStore()
const picker = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const urlOpen = ref(false)
const urlDraft = ref('')
const ocrEnabled = defineModel<boolean>('ocrEnabled', { required: true })
const logo = computed(() => settingsStore.isDark ? darkLogo : lightLogo)

const exampleModules = import.meta.glob('@/assets/images/example/*.{png,jpg,jpeg,webp}', { eager: true, query: '?url', import: 'default' }) as Record<string, string>
const tagMap: Record<string, string[]> = {
  'FPGA表格': ['表格', 'FPGA'],
  '发表论文加分细则': ['细则', '论文'],
  '同步时序逻辑电路实验': ['实验', '电路'],
  '基本素质测评': ['测评', '表格'],
  '数字逻辑拼接图片': ['拼图', '逻辑'],
  '灰名单': ['名单', '文字'],
  '计算机类教学计划': ['教学', '计划'],
}
const examples = Object.entries(exampleModules).map(([path, src]) => {
  const filename = path.split('/').pop() ?? '示例.png'
  const title = filename.replace(/\.[^.]+$/u, '')
  return { filename, title, src, tags: tagMap[title] ?? ['文档'] }
})

/** Forward one unrestricted selected file into the shared upload flow. */
function onPick(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('upload', file)
  if (picker.value) picker.value.value = ''
}

/** Accept one dropped file and clear the visual drag state. */
function onDrop(event: DragEvent): void {
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('upload', file)
}

/** Submit one non-empty URL through the crawler task endpoint. */
function submitUrl(): void {
  const value = urlDraft.value.trim()
  if (!value) return
  emit('crawl', value)
  urlDraft.value = ''
  urlOpen.value = false
}

/** Fetch a bundled asset and submit it through exactly the same upload API. */
async function parseExample(example: { filename: string; src: string }): Promise<void> {
  const response = await fetch(example.src)
  emit('upload', new File([await response.blob()], example.filename, { type: response.headers.get('Content-Type') ?? 'image/png' }), 'example')
}
</script>

<template>
  <section v-if="running" class="scanner-running" aria-live="polite">
    <PixelLoader class="scanner-pixel-loader" />
    <strong>解析中</strong>
    <span>{{ running.stage_label }}</span>
    <div class="scanner-progress" role="progressbar" :aria-valuenow="running.progress" aria-valuemin="0" aria-valuemax="100">
      <i :style="{ transform: `scaleX(${running.progress / 100})` }"></i>
    </div>
    <small>{{ running.progress }}%</small>
  </section>

  <div v-else class="scanner-start">
    <section
      class="scanner-drop-zone"
      :class="{ dragging }"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <button class="scanner-settings" type="button" title="解析设置" aria-label="解析设置"><IcIcon name="settings" :size="16" /></button>
        </DropdownMenuTrigger>
        <DropdownMenuPortal>
          <DropdownMenuContent align="end">
            <DropdownMenuItem @select="ocrEnabled = !ocrEnabled">
              <IcIcon :name="ocrEnabled ? 'check' : 'radio-unchecked'" :size="15" />
              <span>OCR</span><span class="setting-value">{{ ocrEnabled ? '已开启' : '已关闭' }}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenu>
      <img class="scanner-logo" :src="logo" alt="" />
      <div class="scanner-upload-actions">
        <button type="button" @click="picker?.click()"><IcIcon name="paperclip" :size="15" />上传文件</button>
        <button type="button" @click="urlOpen = true"><IcIcon name="language" :size="15" />网页链接</button>
      </div>
      <input ref="picker" hidden type="file" @change="onPick" />
      <p>拖拽文件到此处开始解析</p>
    </section>

    <section class="scanner-examples" aria-labelledby="scanner-examples-title">
      <h2 id="scanner-examples-title"><IcIcon name="image" :size="16" />示例</h2>
      <div class="scanner-example-strip">
        <button v-for="example in examples" :key="example.filename" type="button" class="scanner-example" @click="parseExample(example)">
          <span class="scanner-example-image"><img :src="example.src" :alt="example.title" /></span>
          <span class="scanner-example-copy"><strong>{{ example.title }}</strong><span><i v-for="tag in example.tags" :key="tag">{{ tag }}</i></span></span>
        </button>
      </div>
    </section>
  </div>

  <div v-if="urlOpen" class="scanner-url-backdrop" @click.self="urlOpen = false">
    <form class="scanner-url-dialog" role="dialog" aria-modal="true" aria-label="解析网页链接" @submit.prevent="submitUrl">
      <header><strong>网页链接</strong><button type="button" aria-label="关闭" @click="urlOpen = false"><IcIcon name="close" :size="16" /></button></header>
      <label>链接地址<input v-model="urlDraft" type="url" required autofocus placeholder="https://example.com/article" /></label>
      <footer><button type="button" @click="urlOpen = false">取消</button><button class="primary" type="submit">开始解析</button></footer>
    </form>
  </div>
</template>

<style scoped>
.scanner-start { position: absolute; inset: 0; box-sizing: border-box; display: grid; align-content: start; gap: 28px; width: auto; max-width: 1040px; min-width: 0; margin: 0 auto; padding: clamp(18px, 4vw, 54px); overflow: auto; }
.scanner-drop-zone { position: relative; display: flex; max-width: 100%; min-width: 0; min-height: clamp(300px, 48vh, 520px); flex-direction: column; align-items: center; justify-content: center; border: 1px dashed var(--color-border-strong); border-radius: 22px; background: var(--color-canvas); transition: border-color 180ms ease, background 180ms ease; }
.scanner-drop-zone.dragging { border-color: var(--color-primary); background: var(--color-primary-softer); }
.scanner-settings { position: absolute; top: 14px; right: 14px; display: grid; place-items: center; width: 30px; height: 30px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-secondary); }
.scanner-settings:hover { background: var(--color-primary-softer); color: var(--color-primary); }
.setting-value { margin-left: auto; color: var(--color-text-muted); font-size: 11px; }
.scanner-logo { width: 76px; height: 76px; object-fit: contain; }
.scanner-upload-actions { display: flex; gap: 10px; margin-top: 20px; }
.scanner-upload-actions button { display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 14px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); color: var(--color-text); font: inherit; transition: border-color 150ms ease, background 150ms ease, transform 120ms ease; }
.scanner-upload-actions button:hover { border-color: var(--color-primary); background: var(--color-primary-softer); }
.scanner-upload-actions button:active { transform: scale(.97); }
.scanner-drop-zone p { margin: 12px 0 0; color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }
.scanner-examples { max-width: 100%; min-width: 0; }
.scanner-examples h2 { display: flex; align-items: center; gap: 7px; margin: 0 0 12px; font-size: calc(14px * var(--font-scale)); }
.scanner-example-strip { display: grid; width: 100%; max-width: 100%; min-width: 0; grid-auto-columns: minmax(230px, 31%); grid-auto-flow: column; gap: 14px; padding: 8px 4px 18px; overflow-x: auto; overflow-y: visible; }
.scanner-example { display: grid; grid-template-rows: minmax(150px, 2fr) minmax(72px, 1fr); min-width: 0; padding: 0; overflow: visible; border: 1px solid var(--color-border); border-radius: 17px; background: var(--color-canvas); color: var(--color-text); font: inherit; text-align: left; }
.scanner-example-image { display: grid; place-items: center; min-height: 0; padding: 14px; overflow: visible; }
.scanner-example-image img { width: 100%; height: 100%; max-height: 190px; object-fit: contain; border-radius: 7px; background: white; box-shadow: 0 14px 30px color-mix(in srgb, var(--color-text) 15%, transparent); transform: translateZ(0); transition: transform 240ms cubic-bezier(.16,1,.3,1), box-shadow 240ms ease; }
.scanner-example:hover img { transform: translateY(-9px) rotate(-1.4deg) scale(1.045); box-shadow: 0 20px 38px color-mix(in srgb, var(--color-text) 20%, transparent); }
.scanner-example-copy { display: grid; align-content: center; gap: 8px; padding: 11px 14px; border-top: 1px solid var(--color-border); }
.scanner-example-copy strong { overflow: hidden; font-size: calc(12px * var(--font-scale)); text-overflow: ellipsis; white-space: nowrap; }
.scanner-example-copy span { display: flex; flex-wrap: wrap; gap: 5px; }
.scanner-example-copy i { padding: 2px 6px; border-radius: 4px; background: var(--color-canvas-soft); color: var(--color-text-muted); font-size: calc(9px * var(--font-scale)); font-style: normal; }
.scanner-running { position: absolute; inset: 0; display: grid; place-items: center; align-content: center; min-height: 0; color: var(--color-text); }
.scanner-pixel-loader { transform: scale(1.7); margin-bottom: 28px; }
.scanner-running strong { font-family: 'MinecraftAE Pixel', var(--font-ui); font-size: calc(18px * var(--font-scale)); }
.scanner-running span { margin-top: 8px; color: var(--color-text-muted); font-size: calc(12px * var(--font-scale)); }
.scanner-progress { position: relative; width: min(360px, 70vw); height: 7px; margin-top: 18px; overflow: hidden; border-radius: 4px; background: var(--color-border); }
.scanner-progress i { position: absolute; inset: 0; background: var(--color-primary); transform-origin: left; transition: transform 260ms ease; }
.scanner-running small { margin-top: 7px; color: var(--color-text-muted); }
.scanner-url-backdrop { position: fixed; inset: 0; z-index: 1100; display: grid; place-items: center; padding: 16px; background: rgba(0,0,0,.4); }
.scanner-url-dialog { display: grid; gap: 18px; width: min(520px, 100%); padding: 18px; border: 1px solid var(--color-border); border-radius: 18px; background: var(--color-surface); color: var(--color-text); }
.scanner-url-dialog header,.scanner-url-dialog footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.scanner-url-dialog header button { display: grid; place-items: center; width: 28px; height: 28px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-muted); }
.scanner-url-dialog label { display: grid; gap: 7px; font-size: calc(12px * var(--font-scale)); }
.scanner-url-dialog input { height: 38px; padding: 0 11px; border: 1px solid var(--color-border); border-radius: 8px; outline: 0; background: var(--color-canvas); color: var(--color-text); font: inherit; }
.scanner-url-dialog input:focus { border-color: var(--color-primary); }
.scanner-url-dialog footer { justify-content: flex-end; }
.scanner-url-dialog footer button { min-height: 32px; padding: 0 13px; border: 0; border-radius: 7px; background: var(--color-canvas-soft); color: var(--color-text); }
.scanner-url-dialog footer .primary { background: var(--color-primary); color: white; }
@media (max-width: 768px) { .scanner-start { padding: 16px; } .scanner-example-strip { grid-auto-columns: minmax(210px, 78%); } }
@media (max-width: 480px) { .scanner-drop-zone { min-height: 270px; } .scanner-upload-actions { flex-direction: column; width: min(220px, 72%); } .scanner-upload-actions button { justify-content: center; } }
@media (prefers-reduced-motion: reduce) { .scanner-example-image img,.scanner-progress i { transition: none; } .scanner-example:hover img { transform: none; } }
</style>
