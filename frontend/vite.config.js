import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig( {
  plugins: [ svelte() ],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/analyze': 'http://localhost:8000',
      '/warmup': 'http://localhost:8000',
      '/translation': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/cache': 'http://localhost:8000',
      '/models': 'http://localhost:8000',
    }
  }
} )
