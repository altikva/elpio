# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Dispatcher entrypoint.

"""Dispatcher entrypoint.

``python -m elpio.dispatcher.main`` runs the loop from the ELPIO_* env the
ElpioTask reconciler sets. ``... main tick`` does a one-shot dispatch (a POST to
the handler), which the scheduled-dispatch CronJob invokes.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from elpio.dispatcher.core import Dispatcher, Poster, httpx_poster


def build_from_env() -> Dispatcher:
    broker_type = os.getenv("ELPIO_BROKER_TYPE", "nats")
    address = os.getenv("ELPIO_BROKER_ADDRESS", "")
    queue = os.getenv("ELPIO_QUEUE", "")
    handler = os.getenv("ELPIO_HANDLER_URL", "")
    max_attempts = int(os.getenv("ELPIO_MAX_ATTEMPTS", "3"))
    rate_raw = os.getenv("ELPIO_RATE_LIMIT")
    rate = int(rate_raw) if rate_raw else None

    if broker_type != "redis":
        raise SystemExit(f"dispatcher: broker {broker_type!r} not yet implemented (redis only)")

    from elpio.dispatcher.brokers import RedisBroker

    broker = RedisBroker(address, queue, dlq=os.getenv("ELPIO_DLQ"))
    return Dispatcher(broker, handler, max_attempts=max_attempts, rate_limit=rate)


def tick(poster: Optional[Poster] = None) -> int:
    """One-shot scheduled dispatch: POST a tick to the handler."""
    poster = poster or httpx_poster()
    return poster(os.getenv("ELPIO_HANDLER_URL", ""), {"event": "tick"})


def main(argv: Optional[List[str]] = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "tick":
        tick()
        return
    build_from_env().run()


if __name__ == "__main__":  # pragma: no cover
    main()
