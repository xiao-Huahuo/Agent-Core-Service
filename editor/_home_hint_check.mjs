import { chromium } from '@playwright/test'

const BASE = 'http://127.0.0.1:5173/'
const PROFILE = {
  userId: 'glow-check-user',
  knowledgeDir: 'C:/knowledge',
  activeLibraryId: '',
  knowledgeLibraries: [],
  knowledgeWatchEnabled: false,
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.addInitScript(
  (entries) => {
    for (const [k, v] of entries) localStorage.setItem(k, v)
  },
  [
    ['agent_editor_profile', JSON.stringify(PROFILE)],
    ['agent_editor_theme_mode', 'dark'],
  ],
)
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.home-view', { timeout: 30000 })

// 1. 左上角序号已移除
const indexCount = await page.locator('.carousel-index').count()
console.log('CAROUSEL_INDEX_COUNT:', indexCount)

// 2. 胶囊在右下角(相对 slide 右下方)
const carousel = page.locator('.carousel-block')
const hint = carousel.locator('.carousel-hint').first()
const slide = carousel.locator('.carousel-slide').first()
const hintBox = await hint.boundingBox()
const slideBox = await slide.boundingBox()
const pos = await hint.evaluate((el) => getComputedStyle(el).position)
console.log('HINT_POSITION:', pos)
console.log(
  'HINT_BOTTOM_RIGHT:',
  Math.abs(hintBox.x + hintBox.width - (slideBox.x + slideBox.width)) < 40,
  'rightGapPx:',
  Math.round(slideBox.x + slideBox.width - (hintBox.x + hintBox.width)),
  'bottomGapPx:',
  Math.round(slideBox.y + slideBox.height - (hintBox.y + hintBox.height)),
)

// 3. 副标题仍在第二行,胶囊不与副标题同行
const subBox = await carousel.locator('.carousel-subtitle').first().boundingBox()
console.log('HINT_NOT_IN_SUB_ROW:', hintBox.y > subBox.y + subBox.height - 2)

// 4. hover 光效仍在
await carousel.hover()
await page.waitForTimeout(350)
const glow = await carousel.evaluate((el) => getComputedStyle(el, '::after').opacity)
console.log('CAROUSEL_GLOW_OPACITY:', glow)

await browser.close()
