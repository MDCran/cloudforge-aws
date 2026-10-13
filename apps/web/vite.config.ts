import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/recharts/')) return 'charts';
          if (id.includes('/node_modules/')) return 'vendor';
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts*"],
    setupFiles: ["src/test-setup.ts"],
  },
});
