// @ts-check
import { defineConfig } from "astro/config";
import { fileURLToPath } from "node:url";
import path from "node:path";

import react from "@astrojs/react";
import sentry from "@sentry/astro";
import tailwindcss from "@tailwindcss/vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sentryDsn = process.env.PUBLIC_SENTRY_DSN;
const sentrySourceMapsUploadOptions =
  process.env.SENTRY_AUTH_TOKEN && process.env.SENTRY_ORG && process.env.SENTRY_PROJECT
    ? {
        authToken: process.env.SENTRY_AUTH_TOKEN,
        org: process.env.SENTRY_ORG,
        project: process.env.SENTRY_PROJECT,
      }
    : undefined;

// https://astro.build/config
export default defineConfig({
  integrations: [
    react(),
    sentry({
      enabled: Boolean(sentryDsn),
      sourceMapsUploadOptions: sentrySourceMapsUploadOptions,
    }),
  ],

  vite: {
    cacheDir: process.env.VITE_CACHE_DIR ?? ".astro-cache/vite",
    plugins: [tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
  },
});
