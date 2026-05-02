import * as Sentry from "@sentry/astro";

const sentryDsn = import.meta.env.PUBLIC_SENTRY_DSN;

Sentry.init({
  dsn: sentryDsn,
  // Adds request headers and IP for users, for more info visit:
  // https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options/#sendDefaultPii
  sendDefaultPii: true,
  enabled: Boolean(sentryDsn),
  environment: import.meta.env.PUBLIC_APP_ENVIRONMENT ?? import.meta.env.MODE,
  release: import.meta.env.PUBLIC_APP_RELEASE,
  tracesSampleRate: Number(
    import.meta.env.PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
  ),
});
