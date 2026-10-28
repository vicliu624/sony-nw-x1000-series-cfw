import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: process.env.WEBSITE_BASE_PATH || "/sony-nw-x1000-series-cfw/",
  build: { outDir: "../dist/website", emptyOutDir: true },
});
