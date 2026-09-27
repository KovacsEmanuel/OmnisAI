import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), {
    name: 'omnis-loopback-development-only',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const origin = 'http://127.0.0.1:5173';
        if (request.headers.host !== '127.0.0.1:5173' || (request.headers.origin && request.headers.origin !== origin)) {
          response.writeHead(403).end('Local development origin required');
          return;
        }
        next();
      });
    },
  }],
  envDir: false,
  publicDir: false,
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true, allowedHosts: ['127.0.0.1'], cors: false,
    // The API dev process uses OMNIS_HTTP_PORT=5173, but binds TCP 8765.
    // Preserve Host/Origin; do not turn the proxy into an Origin bypass.
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false },
      '/health': { target: 'http://127.0.0.1:8765', changeOrigin: false } },
  },
  build: { outDir: 'dist', assetsInlineLimit: 0, sourcemap: false },
});
