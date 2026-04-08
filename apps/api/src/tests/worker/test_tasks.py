"""
Tests for Celery worker tasks - email sending.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Tests for send_mail task
# =============================================================================


class TestSendMailTask:
    """Tests for send_mail Celery task."""

    def test_send_mail_task_exists(self):
        """send_mail task should be callable."""
        from src.worker.tasks import send_mail

        assert callable(send_mail)

    def test_send_mail_task_is_celery_task(self):
        """send_mail should be a Celery task."""
        from src.worker.tasks import send_mail

        # Celery tasks have a 'delay' attribute
        assert hasattr(send_mail, "delay")


# =============================================================================
# Tests for send_email_with_template task
# =============================================================================


class TestSendEmailWithTemplateTask:
    """Tests for send_email_with_template Celery task."""

    def test_send_email_with_template_task_exists(self):
        """send_email_with_template task should be callable."""
        from src.worker.tasks import send_email_with_template

        assert callable(send_email_with_template)

    def test_send_email_with_template_is_celery_task(self):
        """send_email_with_template should be a Celery task."""
        from src.worker.tasks import send_email_with_template

        assert hasattr(send_email_with_template, "delay")


# =============================================================================
# Tests for send_email_with_template_async
# =============================================================================


class TestSendEmailWithTemplateAsync:
    """Tests for send_email_with_template_async function."""

    async def test_send_email_with_template_async_calls_fastmail(self):
        """send_email_with_template_async should call fast_mail.send_message."""
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
            call_kwargs = mock_fast_mail.send_message.call_args
            assert call_kwargs is not None
