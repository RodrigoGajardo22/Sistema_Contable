import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // El modo se pasa con `vite --mode dev`, que carga frontend/.env.dev
  const env = loadEnv(mode, process.cwd(), '')

  const devPort = Number(env.VITE_DEV_PORT ?? 5173)
  const hmrClientPort = Number(env.VITE_HMR_CLIENT_PORT ?? 0)

  return {
    plugins: [vue(), vueDevTools()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      // Necesario para que el servidor escuche fuera del contenedor.
      host: true,
      port: devPort,
      strictPort: true,
      // Los bind mounts de Windows a WSL no emiten eventos del filesystem.
      watch: {
        usePolling: true,
        interval: 300,
      },
      // El navegador entra por el gateway (8080), pero Vite escucha en 5173.
      // Sin esto, el WebSocket del HMR apunta al puerto equivocado.
      hmr: hmrClientPort > 0 ? { clientPort: hmrClientPort } : undefined,
      // Permite consumir la API entrando directo a Vite (sin pasar por el gateway).
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET ?? 'http://backend:5000',
          changeOrigin: true,
        },
      },
    },
  }
})
