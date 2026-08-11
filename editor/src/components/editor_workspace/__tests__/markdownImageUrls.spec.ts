/*
 * Markdown preview image URL tests.
 *
 * Usage:
 * Verifies that editor Markdown image references resolve to knowledge raw
 * URLs and that rendered images receive inline/block display classes.
 */

import { describe, expect, it } from 'vitest'

import {
  buildMarkdownDownloadUrl,
  decorateRenderedMarkdownImages,
  isKnowledgeAssetUrl,
  rewriteMarkdownImageUrls,
} from '../markdownImageUrls'

const context = {
  userId: '1',
  currentFilePath: 'notes/diary.md',
}

describe('markdownImageUrls', () => {
  it('marks knowledge raw image URLs as downloads', () => {
    expect(buildMarkdownDownloadUrl('/knowledge/files/raw?user_id=u&path=forms/demo/assets/a.png'))
      .toContain('download=1')
  })

  it('rewrites relative markdown images against the current file directory', () => {
    const html = rewriteMarkdownImageUrls('before ![cat](images/cat.png) after', context)

    expect(html).toContain('/knowledge/files/raw')
    expect(html).toContain('user_id=1')
    expect(html).toContain('path=notes%2Fimages%2Fcat.png')
  })

  it('keeps spaces in image paths while preserving markdown titles', () => {
    const html = rewriteMarkdownImageUrls('![scan](assets/my scan 1.png "扫描件")', context)

    expect(html).toContain('path=notes%2Fassets%2Fmy+scan+1.png')
    expect(html).toContain('> "扫描件")')
  })

  it('keeps backend static asset URLs instead of converting them to raw-file paths', () => {
    const src = '/knowledge/assets/pdf_preview/hash/image_0001.png'
    const html = rewriteMarkdownImageUrls(`![scan](${src})`, context)

    expect(isKnowledgeAssetUrl(src)).toBe(true)
    expect(html).toContain(src)
    expect(html).not.toContain('/knowledge/files/raw')
  })

  it('decorates standalone images as block images and mixed images as inline images', () => {
    const root = document.createElement('div')
    root.innerHTML = `
      <p><img src="images/full.png"></p>
      <p>文字 <img src="images/inline.png"> 继续</p>
    `

    decorateRenderedMarkdownImages(root, context)

    const blockParagraph = root.querySelector('p')
    const inlineParagraph = root.querySelectorAll('p')[1]
    expect(blockParagraph?.classList.contains('markdown-image-block')).toBe(true)
    expect(inlineParagraph?.classList.contains('markdown-image-block')).toBe(false)
    expect(root.querySelectorAll('img.markdown-image')).toHaveLength(2)
    expect(root.querySelector('img')?.getAttribute('src')).toContain('/knowledge/files/raw')
  })
})
