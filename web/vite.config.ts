import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const API_URL = process.env.ADP_API_URL ?? "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // import.meta.url, not __dirname: this file is an ES module.
      "@": fileURLToPath(new URL("./src", import.meta.url)),
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
      // ADP-d3y: a ratchet, not the goal. CI now runs this suite and blocks on it; the
      // thresholds sit at the measured floor (2026-11-15: 59.6 / 55.9 / 50.7 / 62.1) so
      // coverage can only go up. Raise them as tests are added -- the target is 80.
      thresholds: {
        lines: 61,
        branches: 55,
        functions: 50,
        statements: 59,
      },
    },
  },
});
