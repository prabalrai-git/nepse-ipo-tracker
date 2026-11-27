import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// GitHub Pages serves project sites under /<repo-name>/.
// Override with VITE_BASE=/ for Vercel / Cloudflare Pages.
const base = process.env.VITE_BASE ?? '/nepse-ipo-tracker/'

export default defineConfig({
  base,
  plugins: [
    vue(),
    tailwindcss(),
    // Minimal PWA setup; manifest, icons and caching rules are finished in step 5.
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'NEPSE IPO Alert',
        short_name: 'IPO Alert',
        display: 'standalone',
        start_url: base,
        scope: base,
        theme_color: '#0f172a',
        background_color: '#0f172a',
      },
    }),
  ],
})
