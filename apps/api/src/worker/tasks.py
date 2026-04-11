from asgiref.sync import async_to_sync
from celery import Celery
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr

from src.core.config import TEMPLATE_DIR, db_settings, notification_settings
from src.core.logger import get_logger

logger = get_logger(__name__)

fast_mail = FastMail(
    ConnectionConfig(
        **notification_settings.model_dump(),
        TEMPLATE_FOLDER=TEMPLATE_DIR,
    )
)

send_message = async_to_sync(fast_mail.send_message)

"""
Celery tasks for sending emails
"""
app = Celery(
    "api_tasks",
    broker=db_settings.REDIS_URL(9),
    backend=db_settings.REDIS_URL(9),
    broker_connection_retry_on_startup=True,
)


@app.task
def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
):
    """
    Send an email
    """
    send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            body=body,
            subtype=MessageType.plain,
        ),
    )
    logger.info(f"Email sent to {recipients}")
    return "Message Sent!"


@app.task
def send_email_with_template(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
):
    """
    Send an email with a Jinja2 template
    """
    send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            template_body=context,
            subtype=MessageType.html,
        ),
        template_name=template_name,
    )
    logger.info(f"Email sent to {recipients}")
    return "Message Sent!"


async def send_email_with_template_async(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
):
    """
    Send an email with a Jinja2 template. Bypass Celery and send directly, because celery is not supported on windows machines.
    """
    await fast_mail.send_message(
        message=MessageSchema(
            recipients=recipients,
            subject=subject,
            template_body=context,
            subtype=MessageType.html,
        ),
        template_name=template_name,
    )
    logger.info(f"Email sent to {recipients}")
    return "Message Sent!"