from __future__ import annotations
import os, asyncio
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from .services.okx import (
    fetch_funding_rate, fetch_mark_price, fetch_index_ticker,
    fetch_basis_annualized, fetch_open_interest_change, fetch_long_short_ratio
)
from .services.ws_liq import get_liq_ws

load_dotenv()

app = FastAPI(title="tia-derivs-bridge", version="0.1.0")

class DerivsResponse(BaseModel):
    derivs: dict
    market_refs: dict

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/btc-derivs", response_model=DerivsResponse)
async def btc_derivs(
    instId: str = Query(default="BTC-USDT-SWAP"),
    indexId: str = Query(default="BTC-USDT"),
    ccy: str = Query(default="BTC"),
    period: str = Query(default="15m"),
):
    # Fetch en paralelo
    funding_task = asyncio.create_task(fetch_funding_rate(instId))
    mark_task    = asyncio.create_task(fetch_mark_price(instId))
    index_task   = asyncio.create_task(fetch_index_ticker(indexId))
    basis_task   = asyncio.create_task(fetch_basis_annualized(instId, indexId))
    oi_task      = asyncio.create_task(fetch_open_interest_change(ccy, period))
    lsr_task     = asyncio.create_task(fetch_long_short_ratio(ccy, period))

    funding = await funding_task
    mark    = await mark_task
    index   = await index_task
    basis   = await basis_task
    oi_chg  = await oi_task
    lsr     = await lsr_task

    perp_basis_annualized = basis  # premium (mark-index)/index en fracción

    # Clústers de liquidaciones (WS necesita calentarse)
    up_pct = dn_pct = None
    try:
        ws = get_liq_ws(instId)
        mark_px = mark.get("mark_price")
        if mark_px:
            up_pct, dn_pct = ws.nearest_pct(mark_px)
    except Exception:
        pass

    resp = {
        "derivs": {
            "funding_rate": funding.get("funding_rate"),
            "funding_eta_min": funding.get("funding_eta_min"),
            "perp_basis_annualized": perp_basis_annualized,
            "oi_change_15m": oi_chg,
            "long_short_ratio": lsr,
            "nearest_liq_up_pct": up_pct,
            "nearest_liq_dn_pct": dn_pct
        },
        "market_refs": {
            "mark_price": mark.get("mark_price"),
            "index_px": index.get("index_px"),
            "ts": mark.get("ts") or index.get("ts")
        }
    }
    return JSONResponse(resp)
