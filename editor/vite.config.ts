import { fileURLToPath, URL } from 'node:url'

import { defineConfig, type PluginOption } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

const EDITOR_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' http://127.0.0.1:8002 http://localhost:8002",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
].join('; ')

function productionCspPlugin(): PluginOption {
  return {
    name: 'agent-editor-production-csp',
    apply: 'build',
    transformIndexHtml(html) {
      return html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        `<meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <meta http-equiv="Content-Security-Policy" content="${EDITOR_CSP}">`,
      )
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueJsx(), vueDevTools(), productionCspPlugin()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/agent': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            /*
             * Agent SSE must stay uncompressed through the dev proxy.
             * If the proxy asks for compressed responses, chunks can be
             * buffered until the request completes, leaving the Agent panel
             * and observability cards spinning with no intermediate updates.
             */
            proxyReq.removeHeader('accept-encoding')
          })
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache'
            proxyRes.headers['x-accel-buffering'] = 'no'
            proxyRes.headers.connection = 'keep-alive'
          })
        },
      },
      '/knowledge': 'http://127.0.0.1:8002',
      '/sessions': 'http://127.0.0.1:8002',
      '/settings': 'http://127.0.0.1:8002',
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
