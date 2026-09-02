"""Email notification adapter — abstract + fake + optional SMTP."""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

logger = logging.getLogger("forestwatch.customer_alerts.email")


@dataclass(frozen=True)
class EmailSendResult:
    success: bool
    error: str | None = None


class EmailSender(ABC):
    @abstractmethod
    async def send(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> EmailSendResult:
        ...


class FakeEmailSender(EmailSender):
    """In-memory sender for tests."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> EmailSendResult:
        self.sent.append(
            {"recipients": list(recipients), "subject": subject, "body": body}
        )
        return EmailSendResult(success=True)


class SmtpEmailSender(EmailSender):
    """Optional live SMTP adapter — activated only when fully configured."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._use_tls = use_tls

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._from and self._username and self._password)

    async def send(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> EmailSendResult:
        if not recipients:
            return EmailSendResult(success=False, error="no_recipients")
        if not self.is_configured:
            return EmailSendResult(success=False, error="smtp_not_configured")
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = ", ".join(recipients)
            msg.set_content(body)
            with smtplib.SMTP(self._host, self._port, timeout=10) as client:
                if self._use_tls:
                    client.starttls()
                client.login(self._username, self._password)
                client.send_message(msg)
            return EmailSendResult(success=True)
        except Exception as exc:
            logger.warning("SMTP send failed: %s", type(exc).__name__)
            return EmailSendResult(success=False, error=type(exc).__name__)
