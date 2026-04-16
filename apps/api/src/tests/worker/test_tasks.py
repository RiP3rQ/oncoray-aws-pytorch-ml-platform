"""
Tests for worker task helpers and email dispatch.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestSendMailTask:
    """Tests for send_mail Celery task."""

    def test_send_mail_task_exists(self):
        from src.worker.tasks import send_mail

        assert callable(send_mail)

    def test_send_mail_task_is_celery_task(self):
        from src.worker.tasks import send_mail

        assert hasattr(send_mail, "delay")


class TestSendEmailWithTemplateTask:
    """Tests for send_email_with_template Celery task."""

    def test_send_email_with_template_task_exists(self):
        from src.worker.tasks import send_email_with_template

        assert callable(send_email_with_template)

    def test_send_email_with_template_is_celery_task(self):
        from src.worker.tasks import send_email_with_template

        assert hasattr(send_email_with_template, "delay")


class TestSendEmailWithTemplateAsync:
    """Tests for inline email send helper."""

    async def test_send_email_with_template_async_calls_fastmail(self):
        with patch("src.worker.tasks.fast_mail") as mock_fast_mail:
            mock_fast_mail.send_message = AsyncMock()

            from src.worker.tasks import send_email_with_template_async

            await send_email_with_template_async(
                recipients=["test@example.com"],
                subject="Test Subject",
                context={"username": "test"},
                template_name="test_template.html",
            )

            mock_fast_mail.send_message.assert_called_once()


class TestDispatchEmailWithTemplate:
    """Tests for broker-aware email dispatch."""

    async def test_dispatch_queues_task_when_worker_enabled(self):
        with (
            patch("src.worker.tasks.worker_settings") as mock_settings,
            patch("src.worker.tasks.send_email_with_template.delay") as mock_delay,
        ):
            mock_settings.should_dispatch_via_worker = True

            from src.worker.tasks import dispatch_email_with_template

            result = await dispatch_email_with_template(
                recipients=["test@example.com"],
                subject="Test Subject",
                context={"username": "test"},
                template_name="test_template.html",
            )

            mock_delay.assert_called_once()
            assert result == "Message Queued!"

    async def test_dispatch_sends_inline_when_worker_disabled(self):
        with (
            patch("src.worker.tasks.worker_settings") as mock_settings,
            patch(
                "src.worker.tasks.send_email_with_template_async",
                new_callable=AsyncMock,
            ) as mock_send_inline,
        ):
            mock_settings.should_dispatch_via_worker = False
            mock_send_inline.return_value = "Message Sent!"

            from src.worker.tasks import dispatch_email_with_template

            result = await dispatch_email_with_template(
                recipients=["test@example.com"],
                subject="Test Subject",
                context={"username": "test"},
                template_name="test_template.html",
            )

            mock_send_inline.assert_called_once()
            assert result == "Message Sent!"
