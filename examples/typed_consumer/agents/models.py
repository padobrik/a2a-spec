"""The ticket that the triage agent produces, as the resolution agent sees it."""

from pydantic import BaseModel


class Ticket(BaseModel):
    category: str
    priority: str = "low"
    summary: str
