import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    cors: true,
  },
  build: {
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.tsx'),
        map: resolve(__dirname, 'src/mapEntry.tsx'),
      },
    },
  },
})
