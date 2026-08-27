/**
 * 图书馆真实图片判断工具。
 *
 * 使用说明：新建、编辑和页面直接拖放图书时，共享用户指定的
 * png/jpg/jpeg/webp/gif 图片范围，避免各入口产生不同封面行为。
 */

/** User-approved filename extensions for source-image book covers. */
const LIBRARY_SOURCE_IMAGE_EXTENSION = /\.(?:gif|jpe?g|png|webp)$/i
/** MIME equivalents for the same source-image cover formats. */
const LIBRARY_SOURCE_IMAGE_MIME = /^image\/(?:gif|jpeg|png|webp)(?:;|$)/i

/** 判断真实文件能否直接作为图书封面。 */
export function isLibrarySourceImage(fileName: string, mimeType = ''): boolean {
  return LIBRARY_SOURCE_IMAGE_MIME.test(mimeType.trim())
    || LIBRARY_SOURCE_IMAGE_EXTENSION.test(fileName.split(/[?#]/u, 1)[0] ?? '')
}
