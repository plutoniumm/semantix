import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig( {
  plugins: [ svelte() ],
  server: {
    proxy: {
      '/analyze': 'http://localhost:8000',
      '/warmup': 'http://localhost:8000',
    }
  }
} )
