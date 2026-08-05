import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@fontsource/jetbrains-mono'
import 'katex/dist/katex.min.css'

import App from './App.vue'
import { isFloatingWindow } from './floating/isFloating'
import router from './router'
import './assets/main.css'

const app = createApp(App)

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
  }
}

app.use(createPinia())
if (!isFloatingWindow) {
  app.use(router)
}

app.mount('#app')
