# pydantic-ai holdout notes

## Example

examples/pydantic_ai_examples/flight_booking.py. Picked because it is the
example the project's docs list for multi-agent applications
(docs/multi-agent-applications.md:427, docs/examples/flight-booking.md), and it
shows both patterns the docs name: agent delegation (the search agent calls the
extraction agent from a tool) and programmatic hand-off (the search result and
the seat agent's result go to the purchase step). Three agents, four links.
There is no pydantic-graph example in the examples package at this commit.
The medical triage example (medical_agent_delegation.py) was the other option;
it was not used, only one example is scored.

## Links

| link | producer | consumer | source function | data form | expected fields |
|---|---|---|---|---|---|
| L1 | extraction | search (tool return) | extract_flights | list of typed models (`list[FlightDetails]`) | none |
| L2 | search | search (output validator, retry) | validate_output | typed model union `FlightDetails \| NoFlightFound` | origin, destination, date |
| L3 | search | buy (purchase step) | main | same union | none |
| L4 | seat_preference | buy (purchase step) | find_seat | typed model union `SeatPreference \| Failed` | none |

Totals: 4 cases, 3 expected fields.

## Data forms

All outputs are Pydantic models returned as `result.output`. No dicts, no
shared state; deps (`Deps`) carry only the request, never an agent's output.
Free text appears only as prompts.

## Unusual points

- Both union outputs are told apart by `isinstance` (lines 87, 205, 237), not by
  a field. The failure members `NoFlightFound` and `Failed` have no fields, so
  their snapshots are empty objects.
- L1 ends inside the framework: the tool returns the list whole, and the search
  model reads it as a tool return. len() at line 78 is not a field read.
- L2 is a producer reading its own output: the output validator checks it and
  sends errors back to the same agent through ModelRetry.
- In L3 and L4 the outputs are only printed whole (f-string at 210, `!r` at 245).
  `buy_tickets` is the helper the data is passed to; it reads no fields.
- After a "search" answer, main feeds the run's messages back to the search
  agent (`all_messages(output_tool_return_content=...)` at line 221). That is
  framework message history, not a field read, so it is not a case.
- Assumption: the extraction snapshot keeps the real shape, a JSON list at the
  top of `output`, instead of wrapping it under a made-up key. No case reads
  fields of it, so the paths are not affected.
