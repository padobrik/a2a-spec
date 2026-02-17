"""Customer support agent adapters."""

from examples.customer_support.a2a_spec.adapters.triage_adapter import triage_adapter
from examples.customer_support.a2a_spec.adapters.resolution_adapter import resolution_adapter

ADAPTERS = {
    "triage-agent": triage_adapter,
    "resolution-agent": resolution_adapter,
}
