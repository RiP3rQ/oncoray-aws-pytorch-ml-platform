from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from src.core.config import app_settings, observability_settings
from src.core.logger import get_logger

logger = get_logger(__name__)
_CONFIGURED = False
_HTTPX_INSTRUMENTED = False


def configure_observability(app: FastAPI) -> None:
    """Configure OpenTelemetry tracing and request instrumentation."""
    global _CONFIGURED, _HTTPX_INSTRUMENTED

    if not observability_settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled")
        return

    if not _CONFIGURED:
        resource = Resource.create(
            {
                "service.name": observability_settings.OTEL_SERVICE_NAME,
                "deployment.environment": app_settings.APP_ENVIRONMENT,
            }
        )
        provider = TracerProvider(resource=resource)
        if observability_settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=observability_settings.OTEL_EXPORTER_OTLP_ENDPOINT))
            )
        trace.set_tracer_provider(provider)
        LoggingInstrumentor().instrument(set_logging_format=False)
        _CONFIGURED = True

    if not _HTTPX_INSTRUMENTED:
        HTTPXClientInstrumentor().instrument()
        _HTTPX_INSTRUMENTED = True

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=observability_settings.OTEL_EXCLUDED_URLS,
        server_request_hook=_record_route_scope,
    )


def _record_route_scope(span: trace.Span, scope: dict[str, object]) -> None:
    if span.is_recording():
        span.set_attribute("app.route_type", str(scope.get("type", "unknown")))


def record_exception(exc: Exception) -> None:
    """Attach exception details to current active span."""
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
