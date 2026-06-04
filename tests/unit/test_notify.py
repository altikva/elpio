# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Records interactions; usable as a context manager like
#              smtplib.SMTP.

from elpio.notify import (
    NullNotifier,
    SMTPNotifier,
    build_failed,
    quota_exceeded,
    tenant_provisioned,
)


class FakeSMTP:
    """Records interactions; usable as a context manager like smtplib.SMTP."""

    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.tls = False
        self.login_args = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, pwd):
        self.login_args = (user, pwd)

    def send_message(self, msg):
        self.messages.append(msg)


def test_null_notifier_records():
    n = NullNotifier()
    n.send(tenant_provisioned("acme", "team-acme"))
    assert n.sent[0].event == "tenant.provisioned"
    assert "acme" in n.sent[0].subject


def test_event_helpers_shape():
    assert quota_exceeded("acme", "ns").event == "tenant.quota_exceeded"
    assert build_failed("fn", "ns").event == "function.build_failed"


def test_smtp_notifier_sends_with_tls_and_login():
    FakeSMTP.instances.clear()
    notifier = SMTPNotifier(
        "smtp.test",
        2525,
        sender="elpio@altikva.com",
        recipients=["ops@acme.io"],
        username="u",
        password="p",
        smtp_factory=FakeSMTP,
    )
    notifier.send(tenant_provisioned("acme", "team-acme"))
    smtp = FakeSMTP.instances[-1]
    assert (smtp.host, smtp.port) == ("smtp.test", 2525)
    assert smtp.tls is True
    assert smtp.login_args == ("u", "p")
    sent = smtp.messages[0]
    assert sent["To"] == "ops@acme.io"
    assert sent["X-Elpio-Event"] == "tenant.provisioned"


def test_smtp_notifier_drops_when_no_recipients():
    FakeSMTP.instances.clear()
    SMTPNotifier("smtp.test", smtp_factory=FakeSMTP).send(tenant_provisioned("a", "b"))
    assert FakeSMTP.instances == []  # never connected
