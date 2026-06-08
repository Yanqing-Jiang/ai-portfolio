import path from 'node:path';
import { defineConfig } from 'vitest/config';
import mdx from '@mdx-js/rollup';
import remarkGfm from 'remark-gfm';
// MDX plugin matches vite.config.ts so test imports of lib/blog/mdx.ts
// (which globs content/blog/*.mdx) succeed under Vitest. Tests don't need
// the syntax-highlight rehype passes — Shiki adds noticeable startup time
// and isn't required for our SEO/GEO assertions.

export default defineConfig({
  plugins: [
    mdx({
      // @ts-ignore — plugin types not bundled cleanly for ESM
      enforce: 'pre',
      remarkPlugins: [remarkGfm],
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    setupFiles: './vitest.setup.ts',
    globals: true,
    css: true,
    exclude: ['analytics-legacy/**', 'node_modules/**', 'e2e/**', 'tests/e2e/**', '**/*.spec.ts'],
  },
});
