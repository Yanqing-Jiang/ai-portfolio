import path from 'path';
import { defineConfig } from 'vite';
import mdx from '@mdx-js/rollup';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import rehypePrettyCode from 'rehype-pretty-code';

// Shiki theme tuned to the site's slate-950/sky-500 palette.
// `github-dark-default` is close to our `bg-slate-900/40 backdrop-blur` code-block surface; tweak later if needed.
const prettyCodeOptions = {
  theme: 'github-dark-default',
  keepBackground: false, // we draw the background via Tailwind on the wrapper
  defaultLang: 'plaintext',
};

export default defineConfig(({ isSsrBuild }) => ({
  plugins: [
    {
      enforce: 'pre',
      ...mdx({
        providerImportSource: '@mdx-js/react',
        remarkPlugins: [remarkGfm],
        rehypePlugins: [
          rehypeSlug,
          [rehypeAutolinkHeadings, { behavior: 'wrap', properties: { className: ['heading-anchor'] } }],
          [rehypePrettyCode, prettyCodeOptions],
        ],
      }),
    },
  ],

  server: {
    host: 'localhost',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },

  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  build: isSsrBuild
    ? {}
    : {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-framer': ['framer-motion'],
            'vendor-echarts': ['echarts', 'echarts-for-react'],
          },
        },
      },
    },
  ssr: {
    noExternal: ['react-helmet-async'],
  },
}));
