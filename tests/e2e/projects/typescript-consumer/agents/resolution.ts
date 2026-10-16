export async function resolutionAgent(ticket: Triage): Promise<Reply> {
  const { category } = ticket;
  return { queue: category, urgent: ticket.priority === "high", note: ticket.summary?.trim() };
}
