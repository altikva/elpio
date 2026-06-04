# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Notifier seam + SMTP backend.

"""Notifier seam + SMTP backend.

Reconcilers build a ``Notification`` from one of the event helpers and hand it to
a ``Notifier``. ``NullNotifier`` just records (default / tests); ``SMTPNotifier``
sends mail. The SMTP class takes a ``smtp_factory`` so it is unit-testable
without a live mail server.
"""

from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Callable, List, Optional

logger = logging.getLogger("elpio.notify")


@dataclass
class Notification:
    event: str
    subject: str
    body: str
    to: List[str] = field(default_factory=list)


class Notifier(ABC):
    @abstractmethod
    def send(self, n: Notification) -> None: ...


class NullNotifier(Notifier):
    """Logs and records. Default backend and test double."""

    def __init__(self) -> None:
        self.sent: List[Notification] = []

    def send(self, n: Notification) -> None:
        self.sent.append(n)
        logger.info("notify[%s]: %s", n.event, n.subject)


class SMTPNotifier(Notifier):
    def __init__(
        self,
        host: str,
        port: int = 587,
        *,
        sender: str = "elpio@localhost",
        recipients: Optional[List[str]] = None,
        use_tls: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._recipients = recipients or []
        self._use_tls = use_tls
        self._username = username
        self._password = password
        self._smtp_factory = smtp_factory

    def send(self, n: Notification) -> None:
        recipients = n.to or self._recipients
        if not recipients:
            logger.warning("notify[%s]: no recipients, dropping", n.event)
            return
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = n.subject
        msg["X-Elpio-Event"] = n.event
        msg.set_content(n.body)

        with self._smtp_factory(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)


# --- event helpers -------------------------------------------------------------

def tenant_provisioned(name: str, namespace: str, to: Optional[List[str]] = None) -> Notification:
    return Notification(
        event="tenant.provisioned",
        subject=f"Tenant {name} is ready",
        body=f"Tenant {name} was provisioned in namespace {namespace}.",
        to=to or [],
    )


def quota_exceeded(name: str, namespace: str, to: Optional[List[str]] = None) -> Notification:
    return Notification(
        event="tenant.quota_exceeded",
        subject=f"Tenant {name} hit its quota",
        body=f"Tenant {name} (namespace {namespace}) exceeded its ResourceQuota.",
        to=to or [],
    )


def build_failed(function: str, namespace: str, to: Optional[List[str]] = None) -> Notification:
    return Notification(
        event="function.build_failed",
        subject=f"Build failed for {function}",
        body=f"The build pipeline for function {function} in {namespace} failed.",
        to=to or [],
    )
