import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// GitHub Pages serves project sites under /<repo-name>/.
// The deploy workflow sets VITE_BASE from the repo name; use VITE_BASE=/ for Vercel / Cloudflare Pages.
const base = process.env.VITE_BASE ?? '/nepse-ipo-tracker/'

export default defineConfig({
  base,
  plugins: [
    vue(),
    tailwindcss(),
    VitePWA({
      // "prompt": a new version waits until the user taps Reload, so the page never
      // refreshes itself while a countdown is being read.
      registerType: 'prompt',
      includeAssets: ['icon.svg', 'apple-touch-icon.png'],
      manifest: {
        id: base,
        name: 'NEPSE IPO Alert',
        short_name: 'IPO Alert',
        description: 'Open and upcoming NEPSE IPOs for foreign-employment and general-public quotas, with live JST/NPT countdowns.',
        lang: 'en',
        start_url: base,
        scope: base,
        display: 'standalone',
        orientation: 'portrait',
        theme_color: '#fbefd6',
        background_color: '#fbefd6',
        categories: ['finance', 'utilities'],
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'pwa-maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // App shell is precached (works fully offline). The IPO data is deliberately NOT
        // precached: a precached copy would be frozen at build time.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2,webmanifest}'],
        navigateFallback: `${base}index.html`,
        cleanupOutdatedCaches: true,
        // First install takes control of the already-open page, so the data cache and offline
        // support work from the very first visit. Updates still wait for the user's Reload tap.
        clientsClaim: true,
        runtimeCaching: [
          {
            // Always try the network first so alerts-relevant data is fresh; fall back to the
            // last good copy after 4 seconds or when offline.
            urlPattern: /\/data\/ipos\.json/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'ipo-data',
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 2 },
            },
          },
        ],
      },
    }),
  ],
})
