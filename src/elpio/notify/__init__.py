# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Lifecycle notifications.

"""Lifecycle notifications.

A small ``Notifier`` seam plus the events the reconcilers emit (tenant
provisioned, quota exceeded, build failed). The default is a no-op logger; SMTP
is the first real backend.
"""

from elpio.notify.mailer import (
    Notification,
    Notifier,
    NullNotifier,
    SMTPNotifier,
    build_failed,
    quota_exceeded,
    tenant_provisioned,
)

__all__ = [
    "Notification",
    "Notifier",
    "NullNotifier",
    "SMTPNotifier",
    "tenant_provisioned",
    "quota_exceeded",
    "build_failed",
]
