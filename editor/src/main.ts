import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@fontsource/jetbrains-mono'
import 'katex/dist/katex.min.css'

import App from './App.vue'
import { isFloatingWindow } from './floating/isFloating'
import router from './router'
import './assets/main.css'
import './assets/menu-system.css'

const app = createApp(App)

type WindowResizeEdge = 'n' | 'e' | 's' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

function installWindowResizeHandles(desktopApi: AgentEditorDesktopApi): void {
  const edges: WindowResizeEdge[] = ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']
  const layer = document.createElement('div')
  layer.className = 'window-resize-handles'

  for (const edge of edges) {
    const handle = document.createElement('div')
    handle.className = `window-resize-handle window-resize-${edge}`
    handle.addEventListener('pointerdown', async (event) => {
      if (event.button !== 0) return
      event.preventDefault()
      const started = await desktopApi.beginWindowResize(edge, event.screenX, event.screenY)
      if (!started) return
      handle.setPointerCapture(event.pointerId)
      const move = (moveEvent: PointerEvent) => {
        desktopApi.updateWindowResize(moveEvent.screenX, moveEvent.screenY)
      }
      const end = () => {
        desktopApi.endWindowResize()
        window.removeEventListener('pointermove', move)
        window.removeEventListener('pointerup', end)
        window.removeEventListener('pointercancel', end)
      }
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', end)
      window.addEventListener('pointercancel', end)
    })
    layer.appendChild(handle)
  }

  document.body.appendChild(layer)
}

// In the Electron shell the window is transparent and rounded by CSS, so the
// app root carries the border-radius. Maximized windows drop the radius.
const desktopApi = window.agentEditorDesktop
if (desktopApi?.isDesktop) {
  document.documentElement.classList.add('electron-window')
  if (isFloatingWindow) {
    // The floating window keeps the app root fully transparent so the widget's
    // CSS shadow can render in the surrounding gutter.
    document.documentElement.classList.add('floating-window')
  } else {
    const syncMaximized = (maximized: boolean) => {
      document.documentElement.classList.toggle('maximized', maximized)
    }
    desktopApi.onMaximizedChange(syncMaximized)
    installWindowResizeHandles(desktopApi)
  }
}

app.use(createPinia())
if (!isFloatingWindow) {
  app.use(router)
}

app.mount('#app')
