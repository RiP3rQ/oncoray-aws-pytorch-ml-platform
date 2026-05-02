// @ts-check
import { defineConfig } from "astro/config";
import { fileURLToPath } from "node:url";
import path from "node:path";

import react from "@astrojs/react";
import sentry from "@sentry/astro";
import tailwindcss from "@tailwindcss/vite";
import { loadEnv } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const mode =
  process.env.MODE ??
  (process.env.NODE_ENV === "production" ? "production" : "development");
const env = { ...loadEnv(mode, __dirname, ""), ...process.env };
const sentryDsn = env.PUBLIC_SENTRY_DSN;
const sentryRelease = env.SENTRY_RELEASE ?? env.PUBLIC_APP_RELEASE;

if (sentryRelease) {
  process.env.SENTRY_RELEASE ??= sentryRelease;
  process.env.PUBLIC_APP_RELEASE ??= sentryRelease;
}

const sentrySourceMapsUploadOptions =
  env.SENTRY_AUTH_TOKEN && env.SENTRY_ORG && env.SENTRY_PROJECT
    ? {
        authToken: env.SENTRY_AUTH_TOKEN,
        org: env.SENTRY_ORG,
        project: env.SENTRY_PROJECT,
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
    cacheDir: env.VITE_CACHE_DIR ?? ".astro-cache/vite",
    plugins: [tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
  },
});
