import * as Sentry from "@sentry/astro";

const sentryDsn = import.meta.env.PUBLIC_SENTRY_DSN;

Sentry.init({
  dsn: sentryDsn,
  enabled: Boolean(sentryDsn),
  environment: import.meta.env.PUBLIC_APP_ENVIRONMENT ?? import.meta.env.MODE,
  release: import.meta.env.PUBLIC_APP_RELEASE,
  tracesSampleRate: Number(
    import.meta.env.PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
  ),
});
