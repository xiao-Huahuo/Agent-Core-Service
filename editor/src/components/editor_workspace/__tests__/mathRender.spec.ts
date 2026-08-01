import { describe, expect, it } from 'vitest'

import {
  extractDisplayMath,
  extractPreviewMath,
  renderMathInDom,
  renderMathInHtml,
  renderMathInPreviewDom,
} from '../mathRender'

describe('renderMathInHtml', () => {
  it('renders inline math $...$ as katex', () => {
    const out = renderMathInHtml('行内 $1,2,3,\\quad4$ 结束')
    expect(out).toContain('katex')
    expect(out).not.toContain('$1,2,3')
  })

  it('renders display math with standalone $$ lines', () => {
    const out = renderMathInHtml('$$\n\\sum_{i=1}^{5} i^2+2i-1\n$$')
    expect(out).toContain('katex-display')
  })

  it('renders single-line $$...$$ block', () => {
    const out = renderMathInHtml('$$\\sum_{i=1}^{5} i^2+2i-1$$')
    expect(out).toContain('katex-display')
  })

  it('renders cases / overbrace / underbrace without throwing', () => {
    const cases = '$$\\begin{cases} a=b+c \\\\ b=c+2 \\end{cases}$$'
    const over = '$$\\overbrace{1+2+\\cdots+100}$$'
    const under = '$$\\underbrace{a+b+\\cdots+z}$$'
    for (const src of [cases, over, under]) {
      const out = renderMathInHtml(src)
      expect(out).toContain('katex-display')
    }
  })

  it('tolerates the user lenient format (label on same line, chained blocks) without throwing', () => {
    const src = '求和: $$\n\\sum_{i=1}^{5} i^2+2i-1\n求积:$$\n\\prod_{i=1}^{\\infty}\\frac{1}{n^2}'
    const out = renderMathInHtml(src)
    // 尽量渲染,解析失败的部分显示原文而非抛异常
    expect(() => renderMathInHtml(src)).not.toThrow()
    expect(out.length).toBeGreaterThan(0)
  })

  it('does not render $ inside code fences', () => {
    const out = renderMathInHtml('<pre><code>const s = "$5 and $10"</code></pre>')
    expect(out).toContain('$5 and $10')
    expect(out).not.toContain('katex')
  })

  it('does not throw on invalid commands, renders source as error text', () => {
    const out = renderMathInHtml('$\\badd$')
    expect(() => renderMathInHtml('$\\badd$')).not.toThrow()
    expect(out).toContain('katex')
  })

  it('leaves bare currency dollar signs untouched', () => {
    const out = renderMathInHtml('价格 $10 元')
    expect(out).toBe('价格 $10 元')
  })

  it('does not render double-dollar currency like "$10 and $20"', () => {
    const out = renderMathInHtml('价格 $10 和 $20')
    expect(out).toBe('价格 $10 和 $20')
  })

  it('renders $...$ with digit content when properly closed', () => {
    const out = renderMathInHtml('公式 $10$ 元')
    expect(out).toContain('katex')
  })

  it('does not render $...$ glued to a following ascii word (currency-ish)', () => {
    const out = renderMathInHtml('abc$a^2$def')
    expect(out).not.toContain('katex')
  })
})

describe('extractDisplayMath', () => {
  it('extracts display math blocks anywhere, keeping surrounding text', () => {
    const { markdown, blocks } = extractDisplayMath('文字$$x^2$$尾部')
    expect(markdown).toBe('文字MWMATHBLOCK0MW尾部')
    expect(blocks).toEqual(['x^2'])
  })

  it('handles standalone, lenient-label and chained blocks', () => {
    const src = '求和: $$\n\\sum_{i=1}^{5} i^2\n求积:$$\n\\prod_{i=1}^{\\infty}\\frac{1}{n^2}'
    const { markdown, blocks } = extractDisplayMath(src)
    expect(blocks).toHaveLength(1)
    expect(markdown).toContain('MWMATHBLOCK0MW')
    expect(markdown).toContain('\\prod_{i=1}^{\\infty}\\frac{1}{n^2}')
  })

  it('does not extract $$ inside fenced code', () => {
    const src = '```\n$$x^2$$\n```\n\n行内 $$a^2$$'
    const { markdown, blocks } = extractDisplayMath(src)
    expect(blocks).toEqual(['a^2'])
    expect(markdown).toContain('```\n$$x^2$$\n```')
  })

  it('leaves unmatched $$ untouched for Vditor', () => {
    const { markdown, blocks } = extractDisplayMath('只有单个 $$')
    expect(markdown).toBe('只有单个 $$')
    expect(blocks).toEqual([])
  })
})

describe('extractPreviewMath', () => {
  it('protects inline TeX before Markdown parsing can consume backslashes and underscores', () => {
    const { markdown, inlineBlocks, displayBlocks } = extractPreviewMath('括号: $\\left\\{ x_i \\right\\}$ 和 $\\frac{a}{b}$')

    expect(markdown).toBe('括号: MWMATHINLINE0MW 和 MWMATHINLINE1MW')
    expect(inlineBlocks).toEqual(['\\left\\{ x_i \\right\\}', '\\frac{a}{b}'])
    expect(displayBlocks).toEqual([])
  })

  it('treats adjacent inline formulas as inline formulas, not a display block', () => {
    const { markdown, inlineBlocks, displayBlocks } = extractPreviewMath('列向量: $a_1$$\\begin{pmatrix} a \\\\ b \\end{pmatrix}$')

    expect(markdown).toBe('列向量: MWMATHINLINE0MWMWMATHINLINE1MW')
    expect(inlineBlocks).toEqual(['a_1', '\\begin{pmatrix} a \\\\ b \\end{pmatrix}'])
    expect(displayBlocks).toEqual([])
  })
})

describe('renderMathInPreviewDom', () => {
  it('renders the full LaTeX syntax sample used by Markdown preview', () => {
    const sample = String.raw`# Latex数学公式语法
- 上标: $a^2$  下标: $a_2$
- 加减: $a+b$ $a-b$  叉乘: $a \times b$  点乘: $a \cdot b$  两点除: $a \div b$
- 等于: $a=b$  不等于: $a \neq b$  约等于: $a \approx b$  恒等于: $a \equiv b$
- 大于: $a>b$  小于: $a<b$  大于等于: $a \geq b$  小于等于: $a \leq b$  远大于: $a \gg b$  远小于: $a \ll b$
- 绝对值: $|a|$ 阶乘: $a!$
- 分数: $\frac{a}{b}$
$$
\begin{array}{l}
\Psi_{12}=N_1\Phi_{12}=N_1 B_2 S_2 \\
\Psi_{21}=N_2\Phi_{21}=N_2 B_{1中心} S_2
\end{array}
$$
- 平方根: $\sqrt{a}$  高次方根: $\sqrt[n]{a}$
- 对数: $\log_{2}a$   $\ln a$
- 三角函数: $\sin \theta, \cos \theta, \tan \theta$
- 导数: $x'$  微分: $\frac{d}{dx} f(x)$  偏微分: $\frac{\partial f}{\partial a}$
- 括号: $\left( \right), \left[ \right], \left\langle \right\rangle,\left\{ \right\}$
- 强制空格: $1,2,3,\quad4$
- 求和:  $$\sum_{i=1}^{5} i^2+2i-1$$
- 求积:$$\prod_{i=1}^{\infty}\frac{1}{n^2}$$
- 求极限:$$lim_{x \to \infty} f(x)$$
- 求积分:$$\int_{a}^{b} f(x)dx$$
- 多重积分: $$\iint_S f(x,y)dxdy$$  $$\iiint_S f(x,y)dxdy$$
- 曲线积分:$$\oint_C \mathbf{F} \cdot d\mathbf{r} = 0$$
$$
\begin{align}
f(x) & = (a+b)^2 \\
& = a^2+2ab+b^2
\end{align}
$$
$$
\begin{array}{clc}
z & = & a \\
f(x,y,z) & = & x + y + z
\end{array}
$$
- 方程组: $$\begin{cases} a=b+c \\b=c+2 \\c=a-5 \end{cases}$$
- 后置条件:$$f(x)=\begin{cases} 2^x+3^\sqrt{x}+5 & x\ge0 \\ e^x & x<0 \end{cases}$$
$$
\alpha, \beta, \gamma, \delta, \epsilon, \zeta, \eta, \theta,\vartheta, \iota, \kappa, \lambda, \mu, \nu, \xi, \pi,\varpi, \rho,\varrho, \sigma, \tau, \upsilon, \phi,\varphi, \chi, \psi, \omega
$$
$$
\Gamma, \Delta, \Theta, \Lambda, \Xi, \Pi, \Sigma, \Upsilon, \Phi, \Psi, \Omega
$$
- 数域皮肤: $\mathbb{R}, \mathbb{Z}, \mathbb{N},\mathbb{I}$
- 斜体皮肤:$\mathcal{P},\mathcal{R},\mathcal{M},\mathcal{L}$
- frac皮肤:$\mathfrak{c},\mathfrak{g}$
- 矢量皮肤:$\mathbf{a},\mathbf{B},\mathbf{S}$
- 矢量箭头:$\vec{B}, \vec{H}$
- 行向量与列向量: $\left( a_1,a_2,a_3,... \right)$$\begin{pmatrix} a_1 \\ a_2 \\ a_3 \end{pmatrix}$
- 行列式的det: $\det A$
$$
\begin{vmatrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{vmatrix}
$$
$$
\begin{Vmatrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{Vmatrix}
$$
$$
\begin{matrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{matrix}
$$
$$
\begin{bmatrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{bmatrix}
$$
$$
\begin{pmatrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{pmatrix}
$$
$$
\begin{Bmatrix}
a_{11} & a_{12} & a_{13}\\
a_{21} & a_{22} & a_{23}\\
a_{31} & a_{32} & a_{33}
\end{Bmatrix}
$$
$$
\det \begin{pmatrix}
a_{11} & a_{12} & a_{13} & \dots & a_{1n}\\
a_{21} & a_{22} & a_{23} & \dots & a_{2n}\\
\vdots & \vdots & \vdots & \ddots & \vdots
\end{pmatrix}_{n \times n}
$$
$$
\begin{cases}
a + b &= c \\
x- y &= z
\end{cases}
$$
- 集合关系: $a \cup b, a \cap b, x \in A, x \notin B, A \subset B, A \subseteq B$
- 大交集: $$\bigcap_{i=1}^n P_i$$
- 大并集:  $$\bigcup_{i=1}^n P_i$$
- 与或非: $\land,\lor,\neg$
- 反:$\bar{A}$
- 蕴含与等价: $\implies,\iff,\rightarrow,\leftrightarrow,\Leftrightarrow,\Rightarrow$
- 有效结论: $\mapsto$
- 量词: $\exists, \forall,\exists!$
- 空集: $\emptyset$
- 幂集: $\mathcal{P}$
- 无限基数: $\aleph_0$
- 同伦: $\sim$  同构: $\cong$
- 无穷: $\infty$
- 各种点: $\cdot$ $\dots$ $\vdots$ $\ddots$ $\dot{x}$ $\ddot{x}$
- 偏导数: $\partial$  梯度: $\nabla$
- 拟合: $\hat{Z}$
- 普朗克常数: $\hbar$
- 上括号: $$\overbrace{1+2+\cdots+100}$$
- 下括号:$$\underbrace{a+b+\cdots+z}$$
- 下划线:$\underline{A}$  上划线:$\overline{A}$
- 大符号: $\{,\big\{,\Big\{$
$$
\begin{array}{|c|c||c|}
a & b & S \\
\hline
0&0&1\\
0&1&1\\
1&0&1\\
1&1&0
\end{array}
$$
- Chapter: $\S$
- 斜体的l: $\ell$`
    const { markdown, displayBlocks, inlineBlocks } = extractPreviewMath(sample)
    const root = document.createElement('div')
    root.innerHTML = markdown

    renderMathInPreviewDom(root, displayBlocks, inlineBlocks)

    expect(root.querySelectorAll('.katex').length).toBeGreaterThan(50)
    expect(root.querySelectorAll('.katex-display').length).toBeGreaterThan(10)
    expect(root.querySelector('.katex-error')).toBeNull()
    expect(root.textContent).not.toContain('MWMATHBLOCK')
    expect(root.textContent).not.toContain('MWMATHINLINE')
  })

  it('restores block placeholders as katex-display and renders inline math', () => {
    const root = document.createElement('div')
    root.innerHTML = '<p>文字MWMATHBLOCK0MW后置</p><p>行内 $a^2$ 结束</p>'
    renderMathInPreviewDom(root, ['x^2+1'])
    expect(root.querySelector('.katex-display')).not.toBeNull()
    expect(root.querySelectorAll('.katex').length).toBeGreaterThanOrEqual(2)
    expect(root.textContent).not.toContain('MWMATHBLOCK')
    expect(root.textContent).not.toContain('$a^2$')
  })

  it('leaves unknown placeholders untouched', () => {
    const root = document.createElement('div')
    root.innerHTML = '<p>MWMATHBLOCK9MW</p>'
    renderMathInPreviewDom(root, ['x'])
    expect(root.textContent).toContain('MWMATHBLOCK9MW')
  })
})

describe('renderMathInDom', () => {
  it('renders inline and display math in text nodes (Preview scenario)', () => {
    const root = document.createElement('div')
    root.innerHTML = '行内 $a^2$ 与<br>$$\\sum_{i=1}^{n} i$$'
    renderMathInDom(root)

    expect(root.querySelector('.katex')).not.toBeNull()
    expect(root.querySelector('.katex-display')).not.toBeNull()
    expect(root.textContent).not.toContain('$a^2$')
  })

  it('leaves math inside code blocks untouched', () => {
    const root = document.createElement('div')
    root.innerHTML = '<pre><code>const s = "$5";</code></pre>'
    renderMathInDom(root)

    expect(root.querySelector('.katex')).toBeNull()
    expect(root.textContent).toContain('$5')
  })
})
