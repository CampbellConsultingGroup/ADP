import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

const API_URL = process.env.ADP_API_URL ?? "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Forward all /api/ and /health and /metrics calls to the ADP backend.
      // This makes relative fetch('/api/v1/...') work in the browser dev server
      // without needing absolute URLs or CORS configuration.
      "/api": { target: API_URL, changeOrigin: true },
      "/health": { target: API_URL, changeOrigin: true },
      "/metrics": { target: API_URL, changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    exclude: ["**/node_modules/**", "**/e2e/**", "**/*.spec.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      thresholds: {
        lines: 80,
        branches: 80,
        functions: 80,
        statements: 80,
      },
    },
  },
});
