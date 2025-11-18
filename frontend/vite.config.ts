import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          mui: ['@mui/material', '@mui/system', '@mui/styled-engine'],
          charts: ['lightweight-charts'],
          dayjs: ['dayjs'],
        },
      },
    },
  },
  server: {
    hmr: false,
    // open browser to the app (helpful when dev port changes)
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/metrics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Proxy WebSocket to backend so clients can use ws://localhost:5173/ws
      '/ws': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
