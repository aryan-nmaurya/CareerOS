from __future__ import annotations

import json

Event = tuple[str, dict]


class PhaseStreamParser:
    """Incrementally scans accumulating JSON text from a streaming roadmap
    generation and yields (event, data) tuples the instant enough text has
    arrived to know the answer:

      ("meta", {...})   once, as soon as every scalar field plus weekly_goals
                        and final_project are complete (i.e. the moment the
                        "phases" array opens — this is why the roadmap schema
                        requires "phases" to be the last property)
      ("phase", {...})  once per phase, the instant that phase object's
                        closing brace arrives

    Pure — no I/O, no network, no DB. Chunk boundaries are assumed to fall
    at arbitrary byte positions with no regard for JSON structure (verified
    against real Gemini streaming output before this was written), so this
    tracks brace depth char-by-char across the whole accumulated buffer
    rather than trying to parse each chunk in isolation.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._depth = 0
        self._in_string = False
        self._escaped = False
        self._phases_started = False
        self._meta_emitted = False
        self._phase_start: int | None = None

    def feed(self, chunk: str) -> list[Event]:
        events: list[Event] = []
        for ch in chunk:
            self._buffer += ch

            if self._escaped:
                self._escaped = False
                continue
            if ch == "\\" and self._in_string:
                self._escaped = True
                continue
            if ch == '"':
                self._in_string = not self._in_string
                continue
            if self._in_string:
                continue

            if ch == "{":
                if self._depth == 1 and self._phases_started and self._phase_start is None:
                    self._phase_start = len(self._buffer) - 1
                self._depth += 1
            elif ch == "}":
                self._depth -= 1
                if self._depth == 1 and self._phases_started and self._phase_start is not None:
                    raw = self._buffer[self._phase_start :]
                    self._phase_start = None
                    try:
                        events.append(("phase", json.loads(raw)))
                    except json.JSONDecodeError:
                        pass
            elif ch == "[" and self._depth == 1 and not self._phases_started:
                prefix = self._buffer[: len(self._buffer) - 1].rstrip()
                if prefix.endswith('"phases":') or prefix.endswith('"phases" :'):
                    self._phases_started = True
                    if not self._meta_emitted:
                        meta_raw = self._buffer[: self._buffer.rfind('"phases"')]
                        meta_raw = meta_raw.rstrip().rstrip(",") + "}"
                        try:
                            events.append(("meta", json.loads(meta_raw)))
                        except json.JSONDecodeError:
                            pass
                        self._meta_emitted = True

        return events
