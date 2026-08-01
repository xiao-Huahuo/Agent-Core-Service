import katex from 'katex'

const katexOptions = {
  throwOnError: false,
  output: 'html' as const,
  strict: false,
}

// 公式渲染缓存:agent 回答流式高频刷新,同一公式重复渲染直接命中。
const cache = new Map<string, string>()
const MAX_CACHE_ENTRIES = 300

function cleanTeX(tex: string): string {
  // Preview 场景 Vditor 用 <br> 分隔行内文本,清洗成换行再交给 KaTeX;顺带剥离残留 HTML 标签。
  return tex
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    // 兼容用户样本文档里的 Obsidian 宽容写法:3^\sqrt{x}。KaTeX 严格要求
    // superscript 后面是单 token 或分组,这里归一化为 3^{\sqrt{x}}。
    .replace(/\^\\sqrt(\[[^\]]+\])?\{([^{}]+)\}/g, (_m, index: string | undefined, body: string) =>
      `^{\\sqrt${index ?? ''}{${body}}}`,
    )
}

function renderTeX(tex: string, displayMode: boolean): string {
  const clean = cleanTeX(tex)
  const key = `${displayMode ? 'display' : 'inline'}:${clean}`
  let html = cache.get(key)
  if (html === undefined) {
    html = katex.renderToString(clean, { ...katexOptions, displayMode })
    if (cache.size >= MAX_CACHE_ENTRIES) {
      cache.clear()
    }
    cache.set(key, html)
  }
  return html
}

// $$...$$ 块级:非贪婪跨行匹配,可处理独占行、单行 "$$x$$" 以及标签同行/连续块写法。
const BLOCK_MATH_RE = /\$\$([\s\S]+?)\$\$/g
// $...$ 行内:单行匹配,内部首字符非空格(避免 "$10 each" 货币开头);闭合 $ 后不能紧跟
// ASCII 字母/数字/另一个 $(避免 "价格 $10 和 $20" 这类双 $ 货币被当成公式)。开头 $ 前
// 也不能紧跟 ASCII 字母/数字,与 lute 的词边界一致,避免 "abc$x$" 误渲染。
const INLINE_MATH_RE = /(^|[^$\w])\$([^$\n\s][^$\n]*?)\$(?![\w$])/g

// 占位符保护 <pre>/<code> 内部:代码块里的 $ 不做数学渲染。
const PRE_CODE_RE = /<pre[\s\S]*?<\/pre>|<code[\s\S]*?<\/code>/gi

function renderMathInString(input: string): string {
  const blocks: string[] = []
  const guarded = input.replace(PRE_CODE_RE, (block) => {
    const token = `MWMATHHTMLCODE${blocks.length}MW`
    blocks.push(block)
    return token
  })

  let html = guarded
    .replace(BLOCK_MATH_RE, (_m, tex: string) => renderTeX(tex, true))
    .replace(INLINE_MATH_RE, (_m, prefix: string, tex: string) => `${prefix}${renderTeX(tex, false)}`)

  html = html.replace(/MWMATHHTMLCODE(\d+)MW/g, (_m, i: string) => blocks[+i] ?? '')
  return html
}

// Preview 场景专用:Vditor(lute)会把任意位置的 $$ 当块级公式分隔符,`文字$$x$$` 这类
// 写法会被撕裂成 KaTeX ParseError + 散落的文本。因此渲染前把公式提取成纯文本
// 占位符(避开 Vditor),渲染后在 DOM 字符串层还原成 KaTeX。fenced code 里的 $ 不提取。
const CODE_FENCE_RE = /```[\s\S]*?```/g
const DISPLAY_PLACEHOLDER_RE = /MWMATHBLOCK(\d+)MW/g
const INLINE_PLACEHOLDER_RE = /MWMATHINLINE(\d+)MW/g

function isAsciiWord(ch: string | undefined): boolean {
  return ch !== undefined && /[A-Za-z0-9_]/.test(ch)
}

export function extractDisplayMath(md: string): { markdown: string; blocks: string[] } {
  const code: string[] = []
  const withCodeTokens = md.replace(CODE_FENCE_RE, (c) => {
    const token = `MWMATHCODE${code.length}MW`
    code.push(c)
    return token
  })
  const blocks: string[] = []
  const withMathTokens = withCodeTokens.replace(BLOCK_MATH_RE, (_m, tex: string) => {
    const token = `MWMATHBLOCK${blocks.length}MW`
    blocks.push(tex)
    return token
  })
  const markdown = withMathTokens.replace(/MWMATHCODE(\d+)MW/g, (_m, i: string) => code[+i] ?? '')
  return { markdown, blocks }
}

export function extractPreviewMath(md: string): { markdown: string; displayBlocks: string[]; inlineBlocks: string[] } {
  const code: string[] = []
  const withCodeTokens = md.replace(CODE_FENCE_RE, (c) => {
    const token = `MWMATHCODE${code.length}MW`
    code.push(c)
    return token
  })
  const displayBlocks: string[] = []
  const inlineBlocks: string[] = []
  let markdown = ''

  for (let i = 0; i < withCodeTokens.length;) {
    if (withCodeTokens.startsWith('$$', i)) {
      const end = withCodeTokens.indexOf('$$', i + 2)
      if (end !== -1) {
        const token = `MWMATHBLOCK${displayBlocks.length}MW`
        displayBlocks.push(withCodeTokens.slice(i + 2, end))
        markdown += token
        i = end + 2
        continue
      }
    }

    if (withCodeTokens[i] === '$') {
      const prev = i > 0 ? withCodeTokens[i - 1] : undefined
      const next = withCodeTokens[i + 1]
      if (!isAsciiWord(prev) && next !== undefined && next !== '$' && next !== '\n' && !/\s/.test(next)) {
        let matched = false
        for (let end = i + 1; end < withCodeTokens.length && withCodeTokens[end] !== '\n'; end += 1) {
          if (withCodeTokens[end] !== '$' || isAsciiWord(withCodeTokens[end + 1])) {
            continue
          }
          const token = `MWMATHINLINE${inlineBlocks.length}MW`
          inlineBlocks.push(withCodeTokens.slice(i + 1, end))
          markdown += token
          i = end + 1
          matched = true
          break
        }
        if (!matched) {
          markdown += withCodeTokens[i]
          i += 1
        }
        continue
      }
    }

    markdown += withCodeTokens[i]
    i += 1
  }

  markdown = markdown.replace(/MWMATHCODE(\d+)MW/g, (_m, i: string) => code[+i] ?? '')
  return { markdown, displayBlocks, inlineBlocks }
}

export function renderMathInPreviewDom(root: HTMLElement, displayBlocks: string[], inlineBlocks: string[] = []): void {
  if (!root) return
  let html = root.innerHTML
  html = html.replace(DISPLAY_PLACEHOLDER_RE, (_m, i: string) => {
    const tex = displayBlocks[+i]
    return tex === undefined ? _m : renderTeX(tex, true)
  })
  html = html.replace(INLINE_PLACEHOLDER_RE, (_m, i: string) => {
    const tex = inlineBlocks[+i]
    return tex === undefined ? _m : renderTeX(tex, false)
  })
  const rendered = renderMathInString(html)
  if (rendered !== root.innerHTML) {
    root.innerHTML = rendered
  }
}

export function renderMathInHtml(html: string): string {
  return renderMathInString(html)
}

export function renderMathInDom(root: HTMLElement): void {
  if (!root) return
  // 收集"最内层含 $ 的元素"(含 $ 但子元素都不含 $),整体走字符串渲染,
  // 这样 <p> 内被 <br> 分隔的 $$...$$ 也能跨行匹配,不被拆散成文本节点。
  const targets: Element[] = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      const el = node as Element
      if (!(el.textContent ?? '').includes('$')) {
        return NodeFilter.FILTER_REJECT
      }
      const childHasDollar = Array.from(el.children).some((c) =>
        (c.textContent ?? '').includes('$'),
      )
      return childHasDollar ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT
    },
  })
  while (walker.nextNode()) {
    targets.push(walker.currentNode as Element)
  }
  // TreeWalker 不访问根节点自身:根的直接文本若含 $,单独补上。
  const rootHasDollar = (root.textContent ?? '').includes('$')
  const childHasDollar = Array.from(root.children).some((c) =>
    (c.textContent ?? '').includes('$'),
  )
  if (rootHasDollar && !childHasDollar) {
    targets.push(root)
  }
  for (const el of targets) {
    const html = el.innerHTML
    const rendered = renderMathInString(html)
    if (rendered !== html) {
      el.innerHTML = rendered
    }
  }
}
