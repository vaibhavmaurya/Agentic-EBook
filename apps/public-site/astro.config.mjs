// @ts-check
import { defineConfig } from 'astro/config'

// https://astro.build/config
export default defineConfig({
  output: 'static',
  // Site URL set at build time via SITE env var (for sitemap canonical URLs)
  site: process.env.SITE ?? 'http://localhost:4321',
})
