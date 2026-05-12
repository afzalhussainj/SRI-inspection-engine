import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev convenience: React -> Django on port 8000
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/media": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});


