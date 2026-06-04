# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ElpioTask dispatcher.

"""ElpioTask dispatcher.

The worker an ElpioTask runs: it pulls messages off a broker queue and POSTs
each to the handler ElpioService, with retries and an optional rate limit. The
core loop is broker- and transport-agnostic (injectable) so it is unit-testable
without a live broker.
"""

from elpio.dispatcher.core import Dispatcher, Message
from elpio.dispatcher.brokers import MemoryBroker

__all__ = ["Dispatcher", "Message", "MemoryBroker"]
