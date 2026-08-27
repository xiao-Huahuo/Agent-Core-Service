/**
 * 图书馆文件创建 API 请求构造测试。
 *
 * 使用说明：验证页面拖放与新建表单共用的真实文件上传和图书创建请求契约。
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { uploadKnowledgeFile } from '@/api/knowledge'
import { createLibraryBook } from '@/api/library'

describe('Library file creation API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uploads a dropped file into the managed library directory', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ uploaded_path: 'D:/Knowledge/.mw/library/photo.png' }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['image'], 'photo.png', { type: 'image/png' })

    await uploadKnowledgeFile('u1', file, '.mw/library', false, 'rename')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/knowledge/files/upload')
    const form = fetchMock.mock.calls[0]?.[1]?.body as FormData
    expect(form.get('user_id')).toBe('u1')
    expect(form.get('relative_dir')).toBe('.mw/library')
    expect(form.get('file')).toBe(file)
    expect(form.get('auto_ingest')).toBe('false')
    expect(form.get('conflict_strategy')).toBe('rename')
  })

  it('persists source-image mode through the canonical book endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ item: {} }))
    vi.stubGlobal('fetch', fetchMock)

    await createLibraryBook({
      user_id: 'u1',
      content_type: 'knowledge_file',
      source_path: '.mw/library/photo.png',
      cover_mode: 'source_image',
      cover_asset_id: '',
      tags: [],
    })

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/library/items/book')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      content_type: 'knowledge_file',
      source_path: '.mw/library/photo.png',
      cover_mode: 'source_image',
      cover_asset_id: '',
      tags: [],
    })
  })
})
