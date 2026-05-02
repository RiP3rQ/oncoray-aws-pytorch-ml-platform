// @ts-check
import { defineConfig } from "astro/config";
import { fileURLToPath } from "node:url";
import path from "node:path";

import react from "@astrojs/react";
import sentry from "@sentry/astro";
import tailwindcss from "@tailwindcss/vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sentryDsn = process.env.PUBLIC_SENTRY_DSN;
const sentryRelease =
  process.env.SENTRY_RELEASE ?? process.env.PUBLIC_APP_RELEASE;

if (sentryRelease) {
  process.env.SENTRY_RELEASE ??= sentryRelease;
  process.env.PUBLIC_APP_RELEASE ??= sentryRelease;
}

const sentrySourceMapsUploadOptions =
  process.env.SENTRY_AUTH_TOKEN &&
  process.env.SENTRY_ORG &&
  process.env.SENTRY_PROJECT
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
      ...sentrySourceMapsUploadOptions,
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
