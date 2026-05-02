# Core API

## Local OpenTelemetry Traces

Start local dependencies:

```powershell
bun run docker:start
```

Enable API trace export by copying `apps/api/.env.example` to `apps/api/.env`, or set:

```powershell
$env:OTEL_ENABLED = "true"
$env:OTEL_SERVICE_NAME = "core-api"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
```

Run API:

```powershell
bun run --cwd apps/api dev:e2e
```

Open Jaeger UI:

```text
http://localhost:16686
```

Select service `core-api` after sending requests to the API. The local OpenTelemetry Collector also exposes OTLP gRPC
on `localhost:4317`, OTLP HTTP on `localhost:4318`, and health on `localhost:13133`.

To inspect spans printed by the collector debug exporter:

```powershell
bun run otel:logs
```
