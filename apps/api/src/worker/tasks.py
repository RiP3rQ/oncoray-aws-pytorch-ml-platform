from asgiref.sync import async_to_sync
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr

from src.core.config import TEMPLATE_DIR, notification_settings, worker_settings
from src.core.logger import get_logger
from src.worker.celery_app import app

logger = get_logger(__name__)

fast_mail = FastMail(
    ConnectionConfig(
        **notification_settings.model_dump(),
        TEMPLATE_FOLDER=TEMPLATE_DIR,
    )
)

send_message = async_to_sync(fast_mail.send_message)


@app.task
def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
):
    """Send an email."""
    send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            body=body,
            subtype=MessageType.plain,
        ),
    )
    logger.info("Email sent to %s", recipients)
    return "Message Sent!"


@app.task
def send_email_with_template(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
):
    """Send an email with a Jinja2 template."""
    send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            template_body=context,
            subtype=MessageType.html,
        ),
        template_name=template_name,
    )
    logger.info("Email sent to %s", recipients)
    return "Message Sent!"


async def send_email_with_template_async(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
):
    """Send an email inline without going through Celery."""
    await fast_mail.send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            template_body=context,
            subtype=MessageType.html,
        ),
        template_name=template_name,
    )
    logger.info("Email sent to %s", recipients)
    return "Message Sent!"


async def dispatch_email_with_template(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
) -> str:
    """Queue email through Celery when broker is configured, else send inline."""
    if worker_settings.should_dispatch_via_worker:
        send_email_with_template.delay(
            recipients=recipients,
            subject=subject,
            context=context,
            template_name=template_name,
        )
        logger.info("Queued email task for %s", recipients)
        return "Message Queued!"

    return await send_email_with_template_async(
        recipients=recipients,
        subject=subject,
        context=context,
        template_name=template_name,
    )
