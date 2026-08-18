from __future__ import annotations

import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


class EventLogger:
    def __init__(self, path: str | None = None, *, stream: bool = True) -> None:
        self.path = Path(path) if path else None
        self.stream = stream
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **data: Any) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **data,
        }
        line = json.dumps(record, default=str, sort_keys=True, separators=(",", ":"))
        with _LOCK:
            if self.stream:
                print(line, file=sys.stdout, flush=True)
            if self.path:
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line + "\n")
        return record
