import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig(({ isSsrBuild }) => ({
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
