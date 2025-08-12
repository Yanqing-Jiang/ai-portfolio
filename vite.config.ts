import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    
    // Try to get the API key from multiple possible environment variable names
    const geminiApiKey = env.GEMINI_API_KEY || env.VITE_GEMINI_API_KEY || env.API_KEY;
    
    return {
      server: {
        host: 'localhost',
        port: 5173
      },
      define: {
        'process.env.API_KEY': JSON.stringify(geminiApiKey),
        'process.env.GEMINI_API_KEY': JSON.stringify(geminiApiKey),
        'import.meta.env.VITE_GEMINI_API_KEY': JSON.stringify(geminiApiKey)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
