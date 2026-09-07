/**
 * Offline component preview compiler.
 *
 * Usage:
 * Converts a Vue SFC or standalone HTML snippet into iframe srcdoc. Callers
 * must render the result with sandbox="allow-scripts" and no same-origin flag.
 */

import {
  compileScript,
  compileStyle,
  compileTemplate,
  parse,
  type SFCDescriptor,
} from '@vue/compiler-sfc'
import vueRuntimeSource from 'vue/dist/vue.global.prod.js?raw'

import type { ComponentSourceFormat } from '@/types/componentLibrary'

/** Message type emitted by sandbox documents when their rendered content changes size. */
export const COMPONENT_PREVIEW_SIZE_MESSAGE = 'metaweave-component-preview-size'

/** Keep million-character sources usable without compiling them on the browser main thread. */
export const COMPONENT_PREVIEW_MAX_SOURCE_LENGTH = 1_000_000

/** Return whether a source is small enough for responsive in-browser compilation. */
export function canBuildComponentPreview(source: string): boolean {
  return source.length <= COMPONENT_PREVIEW_MAX_SOURCE_LENGTH
}

const PREVIEW_CSP = [
  "default-src 'none'",
  "script-src 'unsafe-inline' blob:",
  "style-src 'unsafe-inline'",
  "img-src data: blob:",
  "font-src data:",
  "media-src data: blob:",
  "connect-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
  "object-src 'none'",
].join('; ')

/** Build one complete, offline preview document for an iframe srcdoc. */
export function buildComponentPreviewDocument(
  source: string,
  sourceFormat: ComponentSourceFormat,
): string {
  if (sourceFormat === 'html') {
    return buildHtmlDocument(source)
  }
  return buildVueDocument(source)
}

/** Add the restrictive preview policy to a complete document or HTML snippet. */
function buildHtmlDocument(source: string): string {
  const head = `${securityMeta()}${baseStyle()}`
  let document: string
  if (/<head(?:\s[^>]*)?>/iu.test(source)) {
    document = source.replace(/<head(\s[^>]*)?>/iu, (match) => `${match}${head}`)
  } else {
    document = `<!doctype html><html><head>${head}</head><body>${source}</body></html>`
  }
  return appendBodyContent(document, sizeReporterScript())
}

/** Compile Vue template, script, and styles without evaluating user code. */
function buildVueDocument(source: string): string {
  const filename = 'ComponentPreview.vue'
  const parsed = parse(source, { filename })
  assertCompilerErrors(parsed.errors)
  const descriptor = parsed.descriptor
  if (!descriptor.template) {
    throw new Error('Vue component requires a <template> block')
  }

  const scopeId = `data-v-${sourceHash(source)}`
  const compiledScript = descriptor.script || descriptor.scriptSetup
    ? compileScript(descriptor, { id: scopeId, genDefaultAs: '__sfc__' })
    : null
  const compiledTemplate = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: scopeId,
    scoped: descriptor.styles.some((style) => style.scoped),
    compilerOptions: { bindingMetadata: compiledScript?.bindings },
  })
  assertCompilerErrors(compiledTemplate.errors)

  const style = compileStyles(descriptor, scopeId)
  const componentScript = rewriteVueModule([
    compiledScript?.content ?? 'const __sfc__ = {}',
    compiledTemplate.code,
    descriptor.styles.some((block) => block.scoped) ? `__sfc__.__scopeId = '${scopeId}'` : '',
    '__sfc__.render = render',
    "Vue.createApp(__sfc__).mount('#app')",
  ].filter(Boolean).join('\n'))

  return `<!doctype html><html><head>${securityMeta()}${baseStyle()}<style>${escapeClosingTag(style, 'style')}</style></head><body><div id="app"></div><script>${escapeClosingTag(vueRuntimeSource, 'script')}</script><script>${escapeClosingTag(componentScript, 'script')}</script>${sizeReporterScript()}</body></html>`
}

/** Compile every SFC style block and surface its first compiler error. */
function compileStyles(descriptor: SFCDescriptor, scopeId: string): string {
  return descriptor.styles.map((block) => {
    const result = compileStyle({
      source: block.content,
      filename: 'ComponentPreview.vue',
      id: scopeId,
      scoped: block.scoped,
    })
    assertCompilerErrors(result.errors)
    return result.code
  }).join('\n')
}

/** Replace Vue ESM imports with the bundled global runtime and reject others. */
function rewriteVueModule(code: string): string {
  const imports = [...code.matchAll(/\bimport\s+[\s\S]*?\s+from\s+['"]([^'"]+)['"]\s*;?/gu)]
  if (imports.some((match) => match[1] !== 'vue') || /\bimport\s*\(/u.test(code)) {
    throw new Error('Only imports from vue are supported in component previews')
  }
  return code
    .replace(/\bimport\s*\{([\s\S]*?)\}\s*from\s*['"]vue['"]\s*;?/gu, (_match, names: string) => (
      `const { ${normalizeVueBindings(names)} } = Vue;`
    ))
    .replace(/\bimport\s+\*\s+as\s+(\w+)\s+from\s*['"]vue['"]\s*;?/gu, 'const $1 = Vue;')
    .replace(/\bimport\s+(\w+)\s+from\s*['"]vue['"]\s*;?/gu, 'const $1 = Vue;')
    .replace(/\bexport\s+function\s+render\b/u, 'function render')
    .replace(/\bexport\s*\{\s*__sfc__\s+as\s+default\s*\}\s*;?/gu, '')
}

/** Normalize compiler-generated named imports into object destructuring syntax. */
function normalizeVueBindings(names: string): string {
  return names
    .split(',')
    .map((name) => name.trim().replace(/\s+as\s+/gu, ': '))
    .filter(Boolean)
    .join(', ')
}

/** Throw one readable error for parser, script, template, or style failures. */
function assertCompilerErrors(errors: Array<string | { message?: string }> | undefined): void {
  const first = errors?.[0]
  if (!first) return
  throw new Error(typeof first === 'string' ? first : (first.message || 'Component compilation failed'))
}

/** Create a compact deterministic scope identifier without adding a hash package. */
function sourceHash(source: string): string {
  let hash = 5381
  for (let index = 0; index < source.length; index += 1) {
    hash = ((hash << 5) + hash) ^ source.charCodeAt(index)
  }
  return (hash >>> 0).toString(36)
}

/** Prevent generated text from ending its containing HTML element early. */
function escapeClosingTag(value: string, tag: 'script' | 'style'): string {
  return value.replace(new RegExp(`</${tag}`, 'giu'), `<\\/${tag}`)
}

/** Insert trusted preview infrastructure before the document's closing body. */
function appendBodyContent(document: string, content: string): string {
  if (/<\/body>/iu.test(document)) {
    return document.replace(/<\/body>/iu, `${content}</body>`)
  }
  return `${document}${content}`
}

/** Return the policy meta inserted before all user-controlled markup. */
function securityMeta(): string {
  return `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><meta name="viewport" content="width=device-width, initial-scale=1">`
}

/** Center components on a transparent, theme-neutral preview canvas. */
function baseStyle(): string {
  return '<style>html,body{width:100%;height:100%;margin:0;overflow:hidden}body{display:grid;place-items:center;box-sizing:border-box;padding:32px 24px;background:transparent;font-family:system-ui,sans-serif}*,*::before,*::after{box-sizing:border-box}</style>'
}

/** Report the intrinsic component bounds without granting the iframe same-origin access. */
function sizeReporterScript(): string {
  return `<script>
    (() => {
      const type = '${COMPONENT_PREVIEW_SIZE_MESSAGE}';
      let frame = 0;
      const report = () => {
        const app = document.getElementById('app');
        const children = app && app.children.length
          ? [...app.children]
          : [...document.body.children].filter((node) => !['SCRIPT', 'STYLE'].includes(node.tagName));
        const viewport = document.documentElement;
        const rects = children.map((node) => {
          const rect = node.getBoundingClientRect();
          const position = getComputedStyle(node).position;
          const viewportCoupled = (position === 'absolute' || position === 'fixed')
            && (Math.abs(rect.width - viewport.clientWidth) <= 1 || Math.abs(rect.height - viewport.clientHeight) <= 1);
          return viewportCoupled ? null : rect;
        }).filter((rect) => rect && (rect.width || rect.height));
        if (!rects.length) return;
        const left = Math.min(...rects.map((rect) => rect.left));
        const right = Math.max(...rects.map((rect) => rect.right));
        const top = Math.min(...rects.map((rect) => rect.top));
        const bottom = Math.max(...rects.map((rect) => rect.bottom));
        parent.postMessage({
          type,
          width: Math.ceil(right - left),
          height: Math.ceil(bottom - top),
        }, '*');
      };
      const schedule = () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => requestAnimationFrame(report));
      };
      new ResizeObserver(schedule).observe(document.body);
      new MutationObserver(schedule).observe(document.body, { attributes: true, childList: true, subtree: true });
      addEventListener('load', schedule);
      schedule();
      setTimeout(schedule, 100);
    })();
  </script>`
}
