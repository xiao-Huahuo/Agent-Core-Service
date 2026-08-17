/*
 * Wiki-link DOM decoration and recursive embed rendering.
 *
 * Usage:
 * MarkdownPreview calls decorateWikiPreview after Vditor finishes rendering.
 * The helper turns literal [[...]] text into navigable anchors and resolves
 * ![[...]] content through the existing knowledge-file API up to five levels.
 */

import DOMPurify from 'dompurify'
import { marked } from 'marked'

import { readKnowledgeFile } from '@/api/knowledge'
import {
  buildRawFileUrl,
  decorateRenderedMarkdownImages,
  rewriteMarkdownImageUrls,
} from '@/components/editor_workspace/markdownImageUrls'
import { renderMathInHtml } from '@/components/editor_workspace/mathRender'
import type { KnowledgeFileNode } from '@/types/knowledge'

import {
  WIKI_EMBED_MAX_DEPTH,
  extractWikiSection,
  findWikiLinkTokens,
  resolveWikiTargetPath,
  type WikiLinkDestination,
} from './wikiLinks'

/** Shared state for one root preview render and all of its nested embeds. */
export interface WikiPreviewContext {
  tree: KnowledgeFileNode[]
  currentPath: string
  userId: string
  cache: Map<string, string>
  depth?: number
}

const IMAGE_EXTENSIONS = new Set(['gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'])

/** Returns a lowercase extension without a dot. */
function extensionOf(path: string): string {
  const name = path.replace(/\\/g, '/').split('/').pop() ?? ''
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLocaleLowerCase() : ''
}

/** Uses alias text when present and otherwise keeps the visible wiki target. */
function wikiLabel(destination: WikiLinkDestination): string {
  if (destination.alias) return destination.alias
  if (destination.blockId) return `${destination.file}^${destination.blockId}`
  if (destination.heading) return `${destination.file}#${destination.heading}`
  return destination.file
}

/** Reads one Markdown file once for the complete recursive render. */
async function readEmbeddedMarkdown(context: WikiPreviewContext, path: string): Promise<string> {
  const cacheKey = `${context.userId}\u0000${path}`
  const cached = context.cache.get(cacheKey)
  if (cached !== undefined) return cached
  const response = await readKnowledgeFile(context.userId, path)
  context.cache.set(cacheKey, response.content)
  return response.content
}

/** Parses and sanitizes embedded Markdown before recursive wiki decoration. */
function renderEmbeddedMarkdown(markdown: string, context: WikiPreviewContext): string {
  const rewritten = rewriteMarkdownImageUrls(markdown, {
    userId: context.userId,
    currentFilePath: context.currentPath,
  })
  const html = marked.parse(rewritten, { async: false, gfm: true, breaks: true }) as string
  return DOMPurify.sanitize(renderMathInHtml(html), {
    ADD_ATTR: ['class', 'target', 'rel'],
    ADD_TAGS: ['span'],
  })
}

/** Creates the small top-right action that opens an embed as a normal file. */
function createEmbedOpenLink(rawDestination: string, resolvedPath: string): HTMLAnchorElement {
  const openLink = document.createElement('a')
  openLink.className = 'wiki-embed-open'
  openLink.href = '#'
  openLink.title = '打开嵌入文件'
  openLink.setAttribute('aria-label', '打开嵌入文件')
  openLink.dataset.wikiDestination = rawDestination
  openLink.dataset.wikiPath = resolvedPath
  openLink.textContent = '↗'
  return openLink
}

/** Loads one embed as a local image or recursively rendered Markdown section. */
async function renderWikiEmbed(
  container: HTMLElement,
  rawDestination: string,
  destination: WikiLinkDestination,
  context: WikiPreviewContext,
): Promise<void> {
  const resolvedPath = resolveWikiTargetPath(destination.file, context.tree, context.currentPath)
  container.dataset.wikiDestination = rawDestination
  container.dataset.wikiPath = resolvedPath
  if (!resolvedPath) {
    container.classList.add('wiki-embed-unresolved')
    container.textContent = `找不到嵌入内容：${wikiLabel(destination)}`
    return
  }
  container.appendChild(createEmbedOpenLink(rawDestination, resolvedPath))
  if (IMAGE_EXTENSIONS.has(extensionOf(resolvedPath))) {
    const image = document.createElement('img')
    image.className = 'markdown-image wiki-embed-image'
    image.alt = destination.alias || resolvedPath.split('/').pop() || resolvedPath
    image.src = buildRawFileUrl(`/${resolvedPath}`, {
      userId: context.userId,
      currentFilePath: context.currentPath,
    })
    container.appendChild(image)
    return
  }
  if (!['md', 'markdown'].includes(extensionOf(resolvedPath))) {
    const message = document.createElement('p')
    message.className = 'wiki-embed-unsupported'
    message.textContent = '当前文件类型不支持内联嵌入，点击右上角打开。'
    container.appendChild(message)
    return
  }
  const depth = context.depth ?? 0
  if (depth >= WIKI_EMBED_MAX_DEPTH) {
    const message = document.createElement('p')
    message.className = 'wiki-embed-limit'
    message.textContent = `嵌入递归已达到 ${WIKI_EMBED_MAX_DEPTH} 层上限。`
    container.appendChild(message)
    return
  }
  try {
    const source = await readEmbeddedMarkdown(context, resolvedPath)
    const section = extractWikiSection(source, destination)
    if (!section) {
      container.classList.add('wiki-embed-unresolved')
      const message = document.createElement('p')
      message.textContent = `找不到嵌入位置：${wikiLabel(destination)}`
      container.appendChild(message)
      return
    }
    const body = document.createElement('div')
    body.className = 'wiki-embed-content'
    body.innerHTML = renderEmbeddedMarkdown(section, { ...context, currentPath: resolvedPath })
    container.appendChild(body)
    decorateRenderedMarkdownImages(body, {
      userId: context.userId,
      currentFilePath: resolvedPath,
    })
    await decorateWikiPreview(body, {
      ...context,
      currentPath: resolvedPath,
      depth: depth + 1,
    })
  } catch {
    container.classList.add('wiki-embed-unresolved')
    const message = document.createElement('p')
    message.textContent = `嵌入内容读取失败：${wikiLabel(destination)}`
    container.appendChild(message)
  }
}

/** Skips code, links, and already-created embeds while walking literal text. */
function shouldSkipWikiText(textNode: Text): boolean {
  return Boolean(textNode.parentElement?.closest('code, pre, a'))
}

/** Decorates all wiki tokens in one rendered Markdown subtree. */
export async function decorateWikiPreview(root: HTMLElement, context: WikiPreviewContext): Promise<void> {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  let current = walker.nextNode()
  while (current) {
    const textNode = current as Text
    if (!shouldSkipWikiText(textNode) && findWikiLinkTokens(textNode.data).length > 0) {
      textNodes.push(textNode)
    }
    current = walker.nextNode()
  }

  const embedJobs: Promise<void>[] = []
  for (const textNode of textNodes) {
    const tokens = findWikiLinkTokens(textNode.data)
    const fragment = document.createDocumentFragment()
    let offset = 0
    for (const token of tokens) {
      if (token.start > offset) fragment.append(document.createTextNode(textNode.data.slice(offset, token.start)))
      const rawDestination = token.raw.replace(/^!?\[\[|\]\]$/gu, '')
      const resolvedPath = resolveWikiTargetPath(token.destination.file, context.tree, context.currentPath)
      if (token.embed) {
        const embed = document.createElement('section')
        embed.className = 'wiki-embed'
        fragment.append(embed)
        embedJobs.push(renderWikiEmbed(embed, rawDestination, token.destination, context))
      } else {
        const link = document.createElement('a')
        link.className = 'wiki-link'
        link.classList.toggle('wiki-link-unresolved', !resolvedPath)
        link.href = '#'
        link.dataset.wikiDestination = rawDestination
        link.dataset.wikiPath = resolvedPath
        link.textContent = wikiLabel(token.destination)
        fragment.append(link)
      }
      offset = token.end
    }
    if (offset < textNode.data.length) fragment.append(document.createTextNode(textNode.data.slice(offset)))
    textNode.replaceWith(fragment)
  }
  await Promise.all(embedJobs)
}
