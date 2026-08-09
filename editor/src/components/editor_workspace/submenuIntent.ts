/*
 * Submenu intent helper.
 *
 * Usage:
 * Keeps a submenu open while the pointer moves through the invisible triangle
 * between the parent menu item and the submenu panel.
 */
import { onBeforeUnmount, type Ref } from 'vue'

interface Point {
  x: number
  y: number
}

interface IntentTriangle {
  origin: Point
  edgeTop: Point
  edgeBottom: Point
}

function sign(point: Point, a: Point, b: Point): number {
  return (point.x - b.x) * (a.y - b.y) - (a.x - b.x) * (point.y - b.y)
}

export function pointInTriangle(point: Point, a: Point, b: Point, c: Point): boolean {
  const d1 = sign(point, a, b)
  const d2 = sign(point, b, c)
  const d3 = sign(point, c, a)
  const hasNegative = d1 < 0 || d2 < 0 || d3 < 0
  const hasPositive = d1 > 0 || d2 > 0 || d3 > 0
  return !(hasNegative && hasPositive)
}

function buildIntentTriangle(event: MouseEvent, parentEl: HTMLElement, submenuEl: HTMLElement): IntentTriangle {
  const parentRect = parentEl.getBoundingClientRect()
  const submenuRect = submenuEl.getBoundingClientRect()
  const opensRight = submenuRect.left >= parentRect.right
  const edgeX = opensRight ? submenuRect.left : submenuRect.right
  return {
    origin: { x: event.clientX, y: event.clientY },
    edgeTop: { x: edgeX, y: submenuRect.top },
    edgeBottom: { x: edgeX, y: submenuRect.bottom },
  }
}

export function useSubmenuIntent(activeKey: Ref<string>) {
  let pendingKey = ''
  let closeTimer = 0
  let triangle: IntentTriangle | null = null
  let parentEl: HTMLElement | null = null
  let submenuEl: HTMLElement | null = null

  function clearCloseTimer() {
    if (closeTimer) {
      window.clearTimeout(closeTimer)
      closeTimer = 0
    }
  }

  function cleanupIntent() {
    clearCloseTimer()
    pendingKey = ''
    triangle = null
    parentEl = null
    submenuEl = null
    document.removeEventListener('mousemove', handleDocumentMouseMove)
  }

  function closePendingSubmenu() {
    if (pendingKey && activeKey.value === pendingKey) {
      activeKey.value = ''
    }
    cleanupIntent()
  }

  function pointInsideIntent(event: MouseEvent): boolean {
    if (!triangle) {
      return false
    }
    return pointInTriangle(
      { x: event.clientX, y: event.clientY },
      triangle.origin,
      triangle.edgeTop,
      triangle.edgeBottom,
    )
  }

  function handleDocumentMouseMove(event: MouseEvent) {
    const target = event.target
    if (target instanceof Node && (parentEl?.contains(target) || submenuEl?.contains(target))) {
      clearCloseTimer()
      return
    }
    if (pointInsideIntent(event)) {
      clearCloseTimer()
      return
    }
    if (!closeTimer) {
      closeTimer = window.setTimeout(closePendingSubmenu, 80)
    }
  }

  function openSubmenu(key: string) {
    cleanupIntent()
    activeKey.value = key
  }

  function keepSubmenuOpen() {
    cleanupIntent()
  }

  function scheduleSubmenuClose(key: string, event: MouseEvent, parent: HTMLElement, submenu: HTMLElement | null) {
    if (activeKey.value !== key || !submenu) {
      return
    }
    cleanupIntent()
    pendingKey = key
    parentEl = parent
    submenuEl = submenu
    triangle = buildIntentTriangle(event, parent, submenu)
    closeTimer = window.setTimeout(closePendingSubmenu, 280)
    document.addEventListener('mousemove', handleDocumentMouseMove)
  }

  onBeforeUnmount(cleanupIntent)

  return {
    openSubmenu,
    keepSubmenuOpen,
    scheduleSubmenuClose,
    closeSubmenu: closePendingSubmenu,
  }
}
