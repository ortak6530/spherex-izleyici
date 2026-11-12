import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev: Vite on :5173 proxies API and WebSocket to FastAPI on :8000.
// Prod: FastAPI serves the built files from frontend/dist (single Render service).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: {
    target: "es2022",
    sourcemap: false,
    // three.js is loaded lazily (React.lazy), so it already lands in its own chunk
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
