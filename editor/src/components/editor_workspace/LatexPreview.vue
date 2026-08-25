<!--
  LaTeX compile and PDF preview surface.

  Usage:
  EditorPane passes real runtime/compile state. Successful PDFs reuse the
  existing MultimodalPreview; lifecycle buttons emit actions to EditorPane.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import MultimodalPreview from '@/components/editor_workspace/MultimodalPreview.vue'
import type { LatexCompileError, LatexCompileResult, LatexRuntimeStatus } from '@/api/latex'

defineOptions({ name: 'LatexPreview' })

defineProps<{
  status: LatexRuntimeStatus | null
  result: LatexCompileResult | null
  compiling: boolean
}>()

const emit = defineEmits<{
  install: []
  cancelInstall: []
  retry: []
  openError: [error: LatexCompileError]
}>()

/** Require explicit user consent before downloading and installing MiKTeX. */
function confirmInstall() {
  const confirmed = window.confirm(
    '当前电脑没有可用的 LaTeX 编译环境。MetaWeave 将从 MiKTeX 官网下载并安装当前用户范围的运行时，下载量约 150–350 MB，是否继续？',
  )
  if (confirmed) emit('install')
}
</script>

<template>
  <section class="latex-preview">
    <div v-if="compiling" class="latex-state" role="status">
      <IcIcon name="autorenew" :size="20" class="state-spinner" />
      <span>正在编译 LaTeX…</span>
    </div>

    <div v-else-if="status && ['downloading', 'installing', 'cancelling'].includes(status.status)" class="latex-state" role="status">
      <div class="install-line">
        <span>{{ status.message || '正在准备 LaTeX 环境' }}</span>
        <strong>{{ status.progress }}%</strong>
      </div>
      <progress :value="status.progress" max="100"></progress>
      <button v-if="status.status !== 'cancelling'" type="button" class="text-action danger" @click="emit('cancelInstall')">取消</button>
    </div>

    <div v-else-if="!status || status.status === 'missing'" class="latex-state missing-state">
      <IcIcon name="dns" :size="22" />
      <span>需要 LaTeX 编译环境才能生成 PDF 预览。</span>
      <button type="button" class="primary-action" @click="confirmInstall">安装 MiKTeX</button>
    </div>

    <div v-else-if="status.status === 'failed'" class="latex-state error-state">
      <IcIcon name="error-outline" :size="22" />
      <span>{{ status.message || 'MiKTeX 安装失败' }}</span>
      <button type="button" class="primary-action" @click="confirmInstall">重试安装</button>
    </div>

    <div v-else-if="result && !result.success" class="latex-errors">
      <header>
        <span>编译失败</span>
        <button type="button" class="text-action" @click="emit('retry')">重新编译</button>
      </header>
      <button
        v-for="(error, index) in result.errors"
        :key="`${error.file}:${error.line}:${index}`"
        type="button"
        class="diagnostic-row"
        @click="emit('openError', error)"
      >
        <span>{{ error.file }}:{{ error.line }}</span>
        <span>{{ error.message }}</span>
      </button>
      <pre class="compile-log">{{ result.output || '编译器没有返回日志。' }}</pre>
    </div>

    <MultimodalPreview v-else-if="result?.preview" :preview="result.preview" />

    <div v-else class="latex-state">
      <span>保存文件或点击 Preview 开始编译。</span>
      <button type="button" class="text-action" @click="emit('retry')">立即编译</button>
    </div>
  </section>
</template>

<style scoped>
.latex-preview {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  container-type: inline-size;
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
}

.latex-state {
  display: grid;
  width: min(520px, calc(100% - 32px));
  margin: auto;
  justify-items: center;
  gap: var(--space-12);
  text-align: center;
}

.state-spinner { animation: spin 900ms linear infinite; }

.install-line {
  display: flex;
  width: 100%;
  justify-content: space-between;
  gap: var(--space-12);
  text-align: left;
}

.install-line strong { font-variant-numeric: tabular-nums; }

progress {
  width: 100%;
  height: 6px;
  accent-color: var(--color-primary);
}

.primary-action,
.text-action {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  cursor: pointer;
}

.primary-action {
  min-height: 30px;
  padding: 0 var(--space-12);
  background: var(--color-primary);
  color: white;
}

.text-action.danger,
.error-state svg { color: var(--color-danger, #c93838); }

.latex-errors {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-12);
}

.latex-errors header {
  display: flex;
  min-height: 32px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  font-weight: 650;
}

.diagnostic-row {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(120px, 30%) 1fr;
  gap: var(--space-10);
  padding: var(--space-8) 0;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.diagnostic-row span:first-child,
.compile-log { font-family: var(--font-code); }

.compile-log {
  margin: var(--space-12) 0 0;
  padding: var(--space-12);
  overflow: auto;
  background: var(--color-code-bg);
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  white-space: pre-wrap;
}

@container (max-width: 520px) {
  .diagnostic-row {
    grid-template-columns: 1fr;
    gap: 3px;
  }

  .latex-state { width: calc(100% - 20px); }
}

@media (prefers-reduced-motion: reduce) {
  .state-spinner { animation: none; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
