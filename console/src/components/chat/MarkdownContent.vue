<!--
  Markdown 渲染组件。
  将 Markdown 文本解析为 HTML,采用工业风直角无阴影样式,
  使用全局设计系统变量 (JetBrains Mono、低饱和冷色、细线边框)。
-->

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

/** 配置 marked: GFM 扩展 + 单换行转 <br> */
marked.setOptions({
  gfm: true,
  breaks: true,
})

const props = defineProps({
  /** 原始 Markdown 文本 */
  content: { type: String, required: true },
  /** 是否正在流式输出 */
  isStreaming: { type: Boolean, default: false },
})

/** 解析 Markdown 为 HTML */
const html = computed(() => marked.parse(props.content || ''))
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
/* ---- 根容器 ---- */
.markdown-body {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--color-text-primary);
  word-break: break-word;
}

/* ---- 段落 ---- */
.markdown-body :deep(p) {
  margin: 0 0 var(--space-8);
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

/* ---- 标题 ---- */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-family: var(--font-mono);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: var(--space-16) 0 var(--space-8);
  line-height: var(--line-height-tight);
}
.markdown-body :deep(h1) { font-size: var(--font-size-xl); }
.markdown-body :deep(h2) { font-size: var(--font-size-lg); }
.markdown-body :deep(h3) { font-size: var(--font-size-md); }
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) { font-size: var(--font-size-sm); }
.markdown-body :deep(h1) + :deep(h2),
.markdown-body :deep(h2) + :deep(h3) {
  margin-top: 0;
}

/* ---- 内联代码 ---- */
.markdown-body :deep(code) {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  background: var(--color-bg-muted);
  padding: 1px 4px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  color: var(--color-text-primary);
}

/* ---- 代码块 ---- */
.markdown-body :deep(pre) {
  margin: var(--space-8) 0;
  padding: var(--space-12) var(--space-16);
  background: var(--color-bg-muted);
  border: 1px solid var(--color-border);
  border-radius: 0;
  overflow-x: auto;
}
.markdown-body :deep(pre code) {
  background: transparent;
  border: none;
  padding: 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-primary);
}

/* ---- 列表 ---- */
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-8) 0;
  padding-left: var(--space-24);
}
.markdown-body :deep(li) {
  margin-bottom: var(--space-4);
}
.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin-top: var(--space-4);
  margin-bottom: 0;
}

/* ---- 引用块 ---- */
.markdown-body :deep(blockquote) {
  margin: var(--space-8) 0;
  padding: var(--space-8) var(--space-12);
  border-left: 2px solid var(--color-accent);
  color: var(--color-text-secondary);
  background: transparent;
  border-radius: 0;
}

/* ---- 链接 ---- */
.markdown-body :deep(a) {
  color: var(--color-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(a:hover) {
  color: var(--color-accent-hover);
}

/* ---- 分割线 ---- */
.markdown-body :deep(hr) {
  margin: var(--space-16) 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

/* ---- 表格 ---- */
.markdown-body :deep(table) {
  width: 100%;
  margin: var(--space-8) 0;
  border-collapse: collapse;
  border: 1px solid var(--color-border);
  border-radius: 0;
  font-size: var(--font-size-xs);
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: var(--space-6) var(--space-10);
  border: 1px solid var(--color-border-light);
  text-align: left;
}
.markdown-body :deep(th) {
  font-weight: var(--font-weight-semibold);
  background: var(--color-bg-muted);
  color: var(--color-text-secondary);
}
.markdown-body :deep(td) {
  color: var(--color-text-primary);
}

/* ---- 图片 ---- */
.markdown-body :deep(img) {
  max-width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 0;
}

/* ---- 加粗 / 斜体 ---- */
.markdown-body :deep(strong) {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.markdown-body :deep(em) {
  font-style: italic;
}

/* ---- 删除线 ---- */
.markdown-body :deep(del) {
  color: var(--color-text-tertiary);
}

/* ---- 任务列表 ---- */
.markdown-body :deep(input[type="checkbox"]) {
  margin-right: var(--space-6);
  accent-color: var(--color-accent);
}
</style>
