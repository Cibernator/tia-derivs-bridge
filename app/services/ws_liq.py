from __future__ import annotations
import os, asyncio, json, time
from collections import deque, defaultdict
from typing import Dict, Optional, Tuple
import websockets

OKX_WS_PUBLIC = os.getenv("OKX_WS_PUBLIC", "wss://ws.okx.com:8443/ws/v5/public")
LIQ_WINDOW_SEC = int(os.getenv("LIQ_WINDOW_SEC", "120"))
LIQ_MIN_CLUSTER_USD = float(os.getenv("LIQ_MIN_CLUSTER_USD", "5000"))

class LiqClusters:
    def __init__(self):
        self.events = deque()  # (ts_sec, price, side, sz_usd)

    def add(self, ts_ms: int, price: float, side: str, sz_usd: float):
        self.events.append((time.time(), price, side, sz_usd))
        self._trim()

    def _trim(self):
        cutoff = time.time() - LIQ_WINDOW_SEC
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def _build_clusters(self, bin_size: float = 10.0):
        up = defaultdict(float)
        dn = defaultdict(float)
        for _, price, side, sz_usd in self.events:
            if sz_usd < LIQ_MIN_CLUSTER_USD:
                continue
            bucket = round(price / bin_size) * bin_size
            if side.lower().startswith("sell"):
                dn[bucket] += sz_usd
            else:
                up[bucket] += sz_usd
        return {"up": dict(up), "dn": dict(dn)}

    def nearest(self, mark: float) -> Tuple[Optional[float], Optional[float]]:
        clusters = self._build_clusters()
        up_levels = [p for p in clusters["up"].keys() if p > mark]
        dn_levels = [p for p in clusters["dn"].keys() if p < mark]
        up_near = min(up_levels) if up_levels else None
        dn_near = max(dn_levels) if dn_levels else None
        up_pct = (up_near - mark)/mark if up_near else None
        dn_pct = (mark - dn_near)/mark if dn_near else None
        return up_pct, dn_pct

class LiqWS:
    def __init__(self, inst_id: str="BTC-USDT-SWAP"):
        self.inst_id = inst_id
        self.clusters = LiqClusters()
        self._task: Optional[asyncio.Task] = None

    async def connect(self):
        while True:
            try:
                async with websockets.connect(OKX_WS_PUBLIC, ping_interval=30, ping_timeout=30) as ws:
                    sub = {"op":"subscribe","args":[{"channel":"liquidation-orders","instId": self.inst_id}]}
                    await ws.send(json.dumps(sub))
                    async for msg in ws:
                        data = json.loads(msg)
                        if data.get("event") == "subscribe":
                            continue
                        dlist = data.get("data") or []
                        for d in dlist:
                            price = float(d.get("px", 0))
                            ts_ms = int(d.get("ts", 0))
                            side = d.get("side", "buy")
                            sz = float(d.get("sz", 0))
                            sz_usd = price * sz
                            self.clusters.add(ts_ms, price, side, sz_usd)
            except Exception:
                await asyncio.sleep(3)

    def start(self):
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.connect())

    def nearest_pct(self, mark: float):
        return self.clusters.nearest(mark)

_ws_registry: Dict[str, LiqWS] = {}

def get_liq_ws(inst_id: str="BTC-USDT-SWAP") -> LiqWS:
    if inst_id not in _ws_registry:
        _ws_registry[inst_id] = LiqWS(inst_id=inst_id)
        _ws_registry[inst_id].start()
    return _ws_registry[inst_id]
