import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build directly into the FastAPI static dir so `make build-ui`
// produces the bundle served at `/`.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../app/static",
    emptyOutDir: true,
  },
});
