import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
// import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "localhost",
    port: 5173,
    // Enable HTTPS in production mode
    https: mode === 'production' ? true : undefined,
    hmr: true,
    // Proxy API requests to avoid CORS issues in development
    proxy: mode === 'development' ? {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    } : undefined,
  },
  plugins: [react()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    // Security: Generate source maps only in development
    sourcemap: mode !== 'production',
    // Minify in production
    minify: mode === 'production' ? 'esbuild' : false,
    // Chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-tabs'],
        },
      },
    },
  },
  // Security: Define strict CSP-compatible settings
  define: {
    // Prevent accidental exposure of env vars
    'process.env': {},
  },
}));
