# sitrepc2/gui/ingest/progress.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class LssProgress:
    total: int
    completed: int
    failed: int = 0
    current_post_id: Optional[int] = None
