from __future__ import annotations

from typing import Any

from celery import Celery

from src.core.config import DatabaseSettings, WorkerSettings, db_settings, worker_settings


def build_celery_runtime_config(
    worker: WorkerSettings,
    database: DatabaseSettings,
) -> dict[str, Any]:
    """Build Celery runtime config from environment-backed settings."""
    broker_url = worker.resolved_broker_url
    result_backend = worker.CELERY_RESULT_BACKEND
    config: dict[str, Any] = {
        "broker_connection_retry_on_startup": True,
        "task_default_queue": worker.resolved_queue_name,
    }

    if worker.uses_sqs:
        transport_options: dict[str, Any] = {
            "region": worker.AWS_REGION,
            "visibility_timeout": worker.CELERY_VISIBILITY_TIMEOUT_SECONDS,
            "wait_time_seconds": worker.CELERY_WAIT_TIME_SECONDS,
            "polling_interval": worker.CELERY_POLLING_INTERVAL_SECONDS,
        }
        if worker.SQS_QUEUE_URL:
            transport_options["predefined_queues"] = {
                worker.resolved_queue_name: {
                    "url": worker.SQS_QUEUE_URL,
                    "region": worker.AWS_REGION,
                }
            }
            config["task_create_missing_queues"] = False

        config["broker_transport_options"] = transport_options
        config["task_ignore_result"] = result_backend is None
    else:
        if result_backend is None:
            result_backend = database.REDIS_URL(9)
        config["task_ignore_result"] = False

    return {
        "broker_url": broker_url,
        "result_backend": result_backend,
        "config": config,
    }


def create_celery_app(
    worker: WorkerSettings = worker_settings,
    database: DatabaseSettings = db_settings,
) -> Celery:
    runtime = build_celery_runtime_config(worker=worker, database=database)
    app = Celery(
        "api_tasks",
        broker=runtime["broker_url"],
        backend=runtime["result_backend"],
    )
    app.conf.update(runtime["config"])
    return app


app = create_celery_app()
