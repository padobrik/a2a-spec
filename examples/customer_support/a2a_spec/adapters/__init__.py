"""Customer support agent adapters."""

from .resolution_adapter import resolution_adapter
from .triage_adapter import triage_adapter

ADAPTERS = {
    "triage-agent": triage_adapter,
    "resolution-agent": resolution_adapter,
}
