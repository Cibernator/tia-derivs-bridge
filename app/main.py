from __future__ import annotations
import os, asyncio, logging
from fastapi import FastAPI, Query
from dotenv import load_dotenv

from .services.okx import (
    fetch_funding_rate, fetch_mark_price, fetch_index_ticker,
    fetch_basis_annualized, fetch_open_interest_change, fetch_long_short_ratio,
    fetch_instrument_meta   # <-- NUEVO
)

from .services.ws_liq import get_liq_ws

load_dotenv()
log = logging.getLogger("uvicorn.error")

app = FastAPI(title="tia-derivs-bridge", version="0.1.1")

@app.get("/")
async def root():
    return {"ok": True, "service": "tia-derivs-bridge"}

@app.get("/health")
async def health():
    return {"ok": True}

async def _safe(coro, name: str):
    try:
        return await coro
    except Exception:
        log.exception(f"{name} failed")
        return None  # devolvemos None para no romper el JSON
from fastapi import Query

@app.get("/meta")
async def get_meta(
    instId: str = Query(..., description="BTC-USDT-SWAP para perp, BTC-USDT para spot"),
    instType: str = Query("SWAP", description="SWAP o SPOT")
):
    meta = await _safe(fetch_instrument_meta(instId, instType), "meta")
    # meta ya viene normalizado; si hubo error, devolvemos defaults seguros
    if not isinstance(meta, dict):
        meta = {"instId": instId, "instType": instType, "tick_size": 0.1, "min_qty": 0.0}
    return {"meta": {
        "instId": meta.get("instId", instId),
        "instType": meta.get("instType", instType),
        "tick_size": meta.get("tick_size", 0.1),
        "min_qty": meta.get("min_qty", 0.0)
    }}

@app.get("/btc-derivs")
async def btc_derivs(
    instId: str = Query(default="BTC-USDT-SWAP"),
    indexId: str = Query(default="BTC-USDT"),
    ccy: str = Query(default="BTC"),
    period: str = Query(default="15m"),
):
    # Ejecutar en paralelo y tolerar errores individuales
    funding, mark, index, basis, oi_chg, lsr = await asyncio.gather(
        _safe(fetch_funding_rate(instId), "funding"),
        _safe(fetch_mark_price(instId), "mark"),
        _safe(fetch_index_ticker(indexId), "index"),
        _safe(fetch_basis_annualized(instId, indexId), "basis"),
        _safe(fetch_open_interest_change(ccy, period), "oi_change"),
        _safe(fetch_long_short_ratio(ccy, period), "long_short_ratio"),
    )

    # Basis: si vino numérico, lo usamos; si no, None
    perp_basis_annualized = basis if isinstance(basis, (int, float)) else None

    # Clústers de liquidaciones (pueden tardar en “calentarse”)
    up_pct = dn_pct = None
    try:
        ws = get_liq_ws(instId)
        mark_px = mark.get("mark_price") if isinstance(mark, dict) else None
        if mark_px:
            up_pct, dn_pct = ws.nearest_pct(mark_px)
    except Exception:
        log.exception("liq nearest failed")

    return {
        "derivs": {
            "funding_rate": (funding or {}).get("funding_rate") if isinstance(funding, dict) else None,
            "funding_eta_min": (funding or {}).get("funding_eta_min") if isinstance(funding, dict) else None,
            "perp_basis_annualized": perp_basis_annualized,
            "oi_change_15m": oi_chg if isinstance(oi_chg, (int, float)) else None,
            "long_short_ratio": lsr if isinstance(lsr, (int, float)) else None,
            "nearest_liq_up_pct": up_pct,
            "nearest_liq_dn_pct": dn_pct
        },
        "market_refs": {
            "mark_price": (mark or {}).get("mark_price") if isinstance(mark, dict) else None,
            "index_px": (index or {}).get("index_px") if isinstance(index, dict) else None,
            "ts": ((mark or {}).get("ts") if isinstance(mark, dict) else None) or ((index or {}).get("ts") if isinstance(index, dict) else None)
        }
    }
