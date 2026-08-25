/*
 * 代码高亮语言注册回归测试。
 *
 * 验证 codeHighlight.ts 注册了 agent 回答、markdown 预览与代码文件预览所需的
 * 全部目标语言及文件扩展名别名,且各语言代码片段可被 highlight.js 高亮并产出
 * 词法 span,避免后续重构悄悄丢语言导致降级为纯文本。
 */
import { describe, expect, it } from 'vitest'

import { hljs, isHighlightableLanguage } from '../codeHighlight'

/** 用户要求覆盖的目标语言及其常用围栏/扩展名写法。 */
const TARGET_LANGUAGES = [
  'go',
  'golang',
  'rust',
  'rs',
  'c',
  'h',
  'cpp',
  'hpp',
  'java',
  'javascript',
  'js',
  'react',
  'kotlin',
  'kt',
  'kts',
  'sql',
  'html',
  'htm',
  'css',
  'vue',
  'jsx',
  'tsx',
  'typescript',
  'ts',
  'python',
  'py',
  'bash',
  'sh',
  'shell',
  'csharp',
  'cs',
  'json',
  'yaml',
  'yml',
  'markdown',
  'md',
  'xml',
  'plaintext',
  'text',
  'latex',
  'tex',
]

/** 每门语言的代表性代码片段,用于验证高亮产出词法 span。 */
const SAMPLES: Array<{ language: string; code: string }> = [
  { language: 'go', code: 'package main\nfunc main() { println("hello") }' },
  { language: 'rust', code: 'fn main() { println!("hello"); }' },
  { language: 'c', code: '#include <stdio.h>\nint main(void) { return 0; }' },
  { language: 'cpp', code: '#include <iostream>\nint main() { std::cout << "hi"; }' },
  { language: 'java', code: 'public class A { public static void main(String[] args) {} }' },
  { language: 'kotlin', code: 'fun main() { println("hi") }' },
  { language: 'sql', code: 'SELECT * FROM users WHERE id = 1;' },
  { language: 'html', code: '<div class="card">hello</div>' },
  { language: 'css', code: '.card { color: #fff; }' },
  { language: 'vue', code: '<template><div>{{ message }}</div></template>' },
  { language: 'jsx', code: 'const App = () => <div className="x">{items.length}</div>;' },
  { language: 'tsx', code: 'const Card: React.FC<{title: string}> = ({ title }) => <b>{title}</b>;' },
  { language: 'tex', code: '\\documentclass{article}\n\\begin{document}$E=mc^2$\\end{document}' },
]

describe('codeHighlight language registration', () => {
  it('registers every target language and alias', () => {
    for (const language of TARGET_LANGUAGES) {
      expect(isHighlightableLanguage(language), `语言 ${language} 应已注册`).toBe(true)
    }
  })

  it('highlights a representative snippet of each requested language into spans', () => {
    for (const { language, code } of SAMPLES) {
      const result = hljs.highlight(code, { language })
      expect(result.value.length, `${language} 高亮输出不应为空`).toBeGreaterThan(0)
      expect(result.value, `${language} 高亮应产出词法 span`).toContain('<span')
    }
  })

  it('treats unknown language identifiers as non-highlightable', () => {
    expect(isHighlightableLanguage('definitely-not-a-language')).toBe(false)
  })
})
