/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_API_BASE_URL?: string;
  readonly PUBLIC_SENTRY_DSN?: string;
  readonly PUBLIC_APP_ENVIRONMENT?: string;
  readonly PUBLIC_APP_RELEASE?: string;
  readonly PUBLIC_SENTRY_TRACES_SAMPLE_RATE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
