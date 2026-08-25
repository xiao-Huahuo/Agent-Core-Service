/**
 * 代码高亮语言注册表。
 *
 * 功能说明:
 * 集中注册 highlight.js core 的目标语言与常见文件扩展名/围栏别名,供 agent 回答
 * (MarkdownContent.vue)、markdown 预览 (MarkdownPreview.vue) 与代码文件预览
 * (CodePreview.vue) 共享。三处消费方共用同一个 hljs 单例,避免各自维护语言列表
 * 导致覆盖不一致。
 *
 * 覆盖语言:go、rust、c、cpp、java、javascript、kotlin、sql、html/css/js 三件套、
 * vue、react(jsx/tsx)等。jsx/tsx 由 javascript/typescript 模块内部自动注册,
 * 此处不做覆盖,以保留其 JSX 特有规则。
 */
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import csharp from 'highlight.js/lib/languages/csharp'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import kotlin from 'highlight.js/lib/languages/kotlin'
import latex from 'highlight.js/lib/languages/latex'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'
import shell from 'highlight.js/lib/languages/shell'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

// ── 基础语言 ──
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('c', c)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('csharp', csharp)
hljs.registerLanguage('css', css)
hljs.registerLanguage('go', go)
hljs.registerLanguage('java', java)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('kotlin', kotlin)
hljs.registerLanguage('latex', latex)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('php', php)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('python', python)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('shell', shell)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('yaml', yaml)

// ── 文件扩展名 / 围栏别名 ──
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('htm', xml)
hljs.registerLanguage('md', markdown)
hljs.registerLanguage('py', python)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('cs', csharp)
hljs.registerLanguage('sh', shell)
hljs.registerLanguage('kt', kotlin)
hljs.registerLanguage('kts', kotlin)
hljs.registerLanguage('rs', rust)
hljs.registerLanguage('vue', xml)
hljs.registerLanguage('react', javascript)
hljs.registerLanguage('golang', go)
hljs.registerLanguage('h', c)
hljs.registerLanguage('hpp', cpp)
hljs.registerLanguage('text', plaintext)
hljs.registerLanguage('tex', latex)

/** 判断指定语言标识是否已注册,未注册时调用方可回退到纯文本。 */
export function isHighlightableLanguage(language: string): boolean {
  return Boolean(hljs.getLanguage(language))
}

export { hljs }
