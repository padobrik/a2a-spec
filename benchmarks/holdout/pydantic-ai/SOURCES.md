# Sources

All snapshots are written by hand. No agent was run. Paths are relative to the
repository root; `fb` is examples/pydantic_ai_examples/flight_booking.py.

| file | repository@short-sha | where the shape and values come from (file:line, test, sample output) |
|---|---|---|
| handshake/snapshots/extraction/sfo_anc_001.json | pydantic/pydantic-ai@11025a1 | Shape: `output_type=list[FlightDetails]` at fb:65-70, `FlightDetails` at fb:29-36 (date as ISO text). Input: `ctx.deps.web_page_text` at fb:77, which is `flights_web_page` at fb:133-181 (main sets it at fb:189). Values: the eight flights on that page, origin and destination reduced to the three-letter codes the field descriptions ask for (fb:34-35). |
| handshake/snapshots/search/sfo_anc_001.json | pydantic/pydantic-ai@11025a1 | Shape: the `FlightDetails` member of `FlightDetails \| NoFlightFound` at fb:52-54, fields at fb:29-36. Input: the prompt f-string at fb:199 with the deps at fb:188-193. Values: the cheapest flight on the page that passes the checks at fb:91-99 (NYC-LA101, $250, SFO to ANC, 2025-01-10, fb:152-156), per the instructions at fb:57-59. |
| handshake/snapshots/search/no_flight_001.json | pydantic/pydantic-ai@11025a1 | Shape: `NoFlightFound` at fb:39-40, a model with no fields, so an empty object; handled at fb:205-207. The date 2025-01-11 in the prompt is a placeholder with no matching flight on the page. |
| handshake/snapshots/seat_preference/window_legroom_001.json | pydantic/pydantic-ai@11025a1 | Shape: the `SeatPreference` member of `SeatPreference \| Failed` at fb:108-110 and fb:118-120. Input and values: the mocked user answer 'window seat with leg room' at tests/test_examples.py:711-712 and the mocked model result `{'row': 1, 'seat': 'A'}` at tests/test_examples.py:927-930. |
| handshake/snapshots/seat_preference/unclear_001.json | pydantic/pydantic-ai@11025a1 | Shape: `Failed` at fb:113-114, a model with no fields, so an empty object; handled at fb:239-241. The input text is a placeholder. |
