from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from src.config import Settings

logger = logging.getLogger(__name__)
_CONFIGURED = False


def configure_observability(app: FastAPI, settings: Settings) -> None:
    """Configure OpenTelemetry tracing for the Model Runtime Host."""
    global _CONFIGURED

    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled")
        return

    if not _CONFIGURED:
        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "deployment.environment": settings.APP_ENVIRONMENT,
            }
        )
        provider = TracerProvider(resource=resource)
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
            )
        trace.set_tracer_provider(provider)
        LoggingInstrumentor().instrument(set_logging_format=False)
        _CONFIGURED = True

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=settings.OTEL_EXCLUDED_URLS,
        server_request_hook=_record_route_scope,
    )


def _record_route_scope(span: trace.Span, scope: dict[str, object]) -> None:
    if span.is_recording():
        span.set_attribute("app.route_type", str(scope.get("type", "unknown")))


def record_exception(exc: Exception) -> None:
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
