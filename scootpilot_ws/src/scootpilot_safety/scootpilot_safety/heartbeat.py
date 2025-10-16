from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class HeartbeatMonitor:
    timeout: float
    last_seen: Dict[str, float] = field(default_factory=dict)

    def ping(self, name: str) -> None:
        self.last_seen[name] = time.time()

    def check(self) -> Dict[str, bool]:
        now = time.time()
        return {name: (now - ts) < self.timeout for name, ts in self.last_seen.items()}
