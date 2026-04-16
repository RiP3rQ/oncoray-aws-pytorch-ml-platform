"""
Tests for Celery broker configuration.
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import DatabaseSettings, WorkerSettings
from src.worker.celery_app import build_celery_runtime_config


class TestBuildCeleryRuntimeConfig:
    """Tests for Celery runtime config generation."""

    def test_redis_default_uses_redis_for_broker_and_backend(self):
        runtime = build_celery_runtime_config(
            worker=WorkerSettings(),
            database=DatabaseSettings(),
        )

        assert runtime["broker_url"].startswith("redis://")
        assert runtime["result_backend"].startswith("redis://")
        assert runtime["config"]["task_default_queue"] == "celery"
        assert runtime["config"]["task_ignore_result"] is False

    def test_sqs_config_uses_queue_url_and_no_result_backend(self):
        runtime = build_celery_runtime_config(
            worker=WorkerSettings(
                AWS_REGION="eu-central-1",
                SQS_QUEUE_URL="https://sqs.eu-central-1.amazonaws.com/123456789012/pytorch-worker",
            ),
            database=DatabaseSettings(),
        )

        assert runtime["broker_url"] == "sqs://"
        assert runtime["result_backend"] is None
        assert runtime["config"]["task_default_queue"] == "pytorch-worker"
        assert runtime["config"]["task_ignore_result"] is True
        assert runtime["config"]["task_create_missing_queues"] is False
        assert runtime["config"]["broker_transport_options"]["region"] == "eu-central-1"
        assert runtime["config"]["broker_transport_options"]["predefined_queues"] == {
            "pytorch-worker": {
                "url": "https://sqs.eu-central-1.amazonaws.com/123456789012/pytorch-worker",
                "region": "eu-central-1",
            }
        }

    def test_custom_result_backend_is_preserved(self):
        runtime = build_celery_runtime_config(
            worker=WorkerSettings(CELERY_RESULT_BACKEND="rpc://"),
            database=DatabaseSettings(),
        )

        assert runtime["result_backend"] == "rpc://"
