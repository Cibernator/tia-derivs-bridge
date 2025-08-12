from __future__ import annotations
import time
from typing import Any, Optional

def now_ms() -> int:
    return int(time.time() * 1000)

def safe_float(v: Any, default: float | None = None) -> Optional[float]:
    try:
        if v is None: return default
        return float(v)
    except Exception:
        return default

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
