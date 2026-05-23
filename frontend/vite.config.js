import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 3000,
        // Proxy /api to backend during dev so the SPA and API share an origin.
        // The frontend can use a relative URL ("/api/...") and avoid CORS in dev.
        proxy: {
            '/api': 'http://localhost:8000',
            '/health': 'http://localhost:8000',
        },
    },
});
