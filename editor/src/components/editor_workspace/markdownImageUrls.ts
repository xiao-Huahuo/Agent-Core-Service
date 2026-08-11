/*
 * Markdown preview image URL helpers.
 *
 * Usage:
 * MarkdownPreview uses these helpers before and after Vditor rendering so
 * knowledge-library relative image paths become backend raw-file URLs while
 * remote, data, blob, and already rewritten URLs are left untouched.
 */

import { buildApiUrl } from '@/api/client'

export interface MarkdownImageUrlContext {
  userId: string
  currentFilePath: string
}

function splitUrlReference(src: string) {
  const normalizedSrc = src.trim().replace(/^<|>$/g, '')
  const hashIndex = normalizedSrc.indexOf('#')
  const queryIndex = normalizedSrc.indexOf('?')
  const indexes = [hashIndex, queryIndex].filter((index) => index >= 0)
  const splitAt = indexes.length > 0 ? Math.min(...indexes) : -1
  return splitAt >= 0 ? normalizedSrc.slice(0, splitAt) : normalizedSrc
}

function decodeUrlPath(path: string) {
  try {
    return decodeURIComponent(path)
  } catch {
    return path
  }
}

function normalizeKnowledgePath(path: string) {
  const parts: string[] = []
  for (const part of path.replace(/\\/g, '/').split('/')) {
    if (!part || part === '.') {
      continue
    }
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/')
}

function resolveMarkdownAssetPath(currentFilePath: string, rawSrc: string) {
  const srcPath = decodeUrlPath(splitUrlReference(rawSrc)).replace(/\\/g, '/')
  if (!srcPath) {
    return ''
  }
  if (srcPath.startsWith('/')) {
    return normalizeKnowledgePath(srcPath)
  }
  const normalizedFilePath = currentFilePath.replace(/\\/g, '/')
  const parentDir = normalizedFilePath.includes('/')
    ? normalizedFilePath.substring(0, normalizedFilePath.lastIndexOf('/') + 1)
    : ''
  return normalizeKnowledgePath(parentDir + srcPath)
}

export function isBrowserHandledAssetUrl(src: string) {
  return /^(https?:|data:|blob:|file:|about:|\/\/|#)/i.test(src)
}

export function isRootRelativeAssetUrl(src: string) {
  return src.startsWith('/') && !src.startsWith('//')
}

export function isKnowledgeRawUrl(src: string) {
  return src.includes('/knowledge/files/raw')
}

/** 判断后端静态挂载的 PDF/DOCX 图片资源 URL。 */
export function isKnowledgeAssetUrl(src: string) {
  return /^\/knowledge\/assets\//i.test(src)
}

/** Adds the backend attachment flag to knowledge-library image URLs. */
export function buildMarkdownDownloadUrl(src: string): string {
  try {
    const url = new URL(src, window.location.origin)
    if (isKnowledgeRawUrl(url.pathname)) {
      url.searchParams.set('download', '1')
    }
    return url.toString()
  } catch {
    return src
  }
}

export function buildRawFileUrl(rawSrc: string, context: MarkdownImageUrlContext) {
  if (!context.currentFilePath || !context.userId || isKnowledgeRawUrl(rawSrc)) {
    return rawSrc
  }
  if (isKnowledgeAssetUrl(rawSrc)) {
    return buildApiUrl(rawSrc)
  }
  if (isBrowserHandledAssetUrl(rawSrc) && !isRootRelativeAssetUrl(rawSrc)) {
    return rawSrc
  }
  const rawPath = resolveMarkdownAssetPath(context.currentFilePath, rawSrc)
  if (!rawPath) {
    return rawSrc
  }
  return buildApiUrl('/knowledge/files/raw', {
    user_id: context.userId,
    path: rawPath,
  })
}

function splitMarkdownImageDestination(rawDestination: string) {
  const destination = rawDestination.trim()
  if (!destination) {
    return { src: '', title: '' }
  }
  if (destination.startsWith('<')) {
    const closeIndex = destination.indexOf('>')
    if (closeIndex >= 0) {
      return {
        src: destination.slice(1, closeIndex),
        title: destination.slice(closeIndex + 1),
      }
    }
  }
  const titleMatch = destination.match(/^(.+?)(\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))$/)
  if (titleMatch) {
    return { src: (titleMatch[1] ?? '').trim(), title: titleMatch[2] ?? '' }
  }
  return { src: destination, title: '' }
}

export function rewriteMarkdownImageUrls(content: string, context: MarkdownImageUrlContext) {
  let nextContent = content.replace(
    /(!\[[^\]]*]\(\s*)([^)\n]*)(\s*\))/g,
    (_match, prefix: string, rawDestination: string, closing: string) => {
      const { src, title } = splitMarkdownImageDestination(rawDestination)
      if (!src) {
        return `${prefix}${rawDestination}${closing}`
      }
      return `${prefix}<${buildRawFileUrl(src, context)}>${title}${closing}`
    },
  )
  nextContent = nextContent.replace(
    /(<img\b[^>]*\bsrc=["'])([^"']+)(["'][^>]*>)/gi,
    (_match, prefix: string, rawSrc: string, suffix: string) => {
      return `${prefix}${buildRawFileUrl(rawSrc, context)}${suffix}`
    },
  )
  return nextContent
}

export function decorateRenderedMarkdownImages(root: HTMLElement, context: MarkdownImageUrlContext) {
  const imgs = root.querySelectorAll<HTMLImageElement>('img[src]')
  for (const img of imgs) {
    const src = img.getAttribute('src') || ''
    if (!((isBrowserHandledAssetUrl(src) && !isRootRelativeAssetUrl(src)) || isKnowledgeRawUrl(src) || isKnowledgeAssetUrl(src))) {
      img.src = buildRawFileUrl(src, context)
    } else if (isKnowledgeAssetUrl(src)) {
      img.src = buildApiUrl(src)
    }
    img.classList.add('markdown-image')
    const parent = img.parentElement
    if (parent?.tagName.toLowerCase() !== 'p') {
      continue
    }
    const hasOnlyImages = [...parent.childNodes].every((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        return !node.textContent?.trim()
      }
      return node instanceof HTMLImageElement || node.nodeName.toLowerCase() === 'br'
    })
    parent.classList.toggle('markdown-image-block', hasOnlyImages)
  }
}
