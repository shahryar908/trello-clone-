import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // host: true listens on 0.0.0.0 (required inside a container);
  // allowedHosts lets the dev server answer requests for tack.local
  server: { port: 5173, host: true, allowedHosts: ["tack.local", "localhost"] },
});
