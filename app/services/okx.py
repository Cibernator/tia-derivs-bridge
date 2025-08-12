from __future__ import annotations
import os
import httpx
from typing import Any, Dict, Optional
from .cache import default_cache
from ..utils import safe_float, now_ms

OKX_BASE_URL = os.getenv("OKX_BASE_URL", "https://www.okx.com")
USE_RUBIK = os.getenv("USE_RUBIK", "0") == "1"

_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=OKX_BASE_URL, timeout=10)
    return _client

async def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    cache_key = f"GET:{path}:{str(sorted(params.items()))}"
    cached = default_cache.get(cache_key)
    if cached is not None:
        return cached
    client = get_client()
    r = await client.get(path, params=params)
    r.raise_for_status()
    data = r.json()
    default_cache.set(cache_key, data)
    return data

async def fetch_funding_rate(inst_id: str) -> Dict[str, Any]:
    resp = await _get("/api/v5/public/funding-rate", {"instId": inst_id})
    d = (resp.get("data") or [{}])[0]
    fr = safe_float(d.get("fundingRate"), 0.0)
    nft = d.get("nextFundingTime") or d.get("fundingTime")
    try:
        nft_ms = int(nft)
        eta_min = max(0, (nft_ms - now_ms()) // 60000)
    except Exception:
        eta_min = None
    return {"funding_rate": fr, "funding_eta_min": eta_min, "raw": d}

async def fetch_mark_price(inst_id: str) -> Dict[str, Any]:
    resp = await _get("/api/v5/public/mark-price", {"instType":"SWAP", "instId": inst_id})
    d = (resp.get("data") or [{}])[0]
    mark = safe_float(d.get("markPx"))
    ts = d.get("ts")
    return {"mark_price": mark, "ts": ts, "raw": d}

async def fetch_index_ticker(index_inst: str="BTC-USDT") -> Dict[str, Any]:
    resp = await _get("/api/v5/market/index-tickers", {"instId": index_inst})
    d = (resp.get("data") or [{}])[0]
    idx = safe_float(d.get("idxPx"))
    ts = d.get("ts")
    return {"index_px": idx, "ts": ts, "raw": d}

async def fetch_basis_annualized(inst_id: str="BTC-USDT-SWAP", index_inst: str="BTC-USDT") -> Optional[float]:
    mark = (await fetch_mark_price(inst_id)).get("mark_price")
    idx  = (await fetch_index_ticker(index_inst)).get("index_px")
    if mark is None or idx in (None, 0):
        return None
    premium = (mark - idx) / idx  # fracción
    return premium

async def fetch_open_interest_change(ccy: str="BTC", period: str="15m") -> Optional[float]:
    if USE_RUBIK:
        resp = await _get("/api/v5/rubik/stat/contracts/open-interest-volume", {"ccy": ccy, "period": period})
        arr = resp.get("data") or []
        if len(arr) >= 2:
            oi_t  = float(arr[-1][1])
            oi_15 = float(arr[-2][1])  # con 5m usarías -3
            if oi_15 != 0:
                return (oi_t - oi_15) / oi_15 * 100.0
        return None
    # Fallback snapshot (aprox; no garantiza 15m exactos)
    snap = await _get("/api/v5/public/open-interest", {"instType":"SWAP", "ccy": ccy})
    d = (snap.get("data") or [{}])[0]
    oi = safe_float(d.get("oi"))
    key = f"oi:{ccy}"
    prev = default_cache.get(key)
    default_cache.set(key, {"ts": now_ms(), "oi": oi})
    if prev and oi and prev.get("oi"):
        try:
            return (oi - prev["oi"]) / prev["oi"] * 100.0
        except ZeroDivisionError:
            return None
    return None

async def fetch_long_short_ratio(ccy: str="BTC", period: str="15m") -> Optional[float]:
    if USE_RUBIK:
        resp = await _get("/api/v5/rubik/stat/contracts/long-short-account-ratio", {"ccy": ccy, "period": period})
        arr = resp.get("data") or []
        if arr:
            try:
                return float(arr[-1][1])
            except Exception:
                return None
    return None
