import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'url';
import path from 'path';

// Fix for __dirname in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // This explicitly handles the JSX transformation to avoid the warning
  esbuild: {
    jsx: 'automatic', 
  },
  server: {
    port: 5173,
    host: true, // Useful for local network testing
  },
});