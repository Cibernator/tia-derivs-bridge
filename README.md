# tia-derivs-bridge

Microservicio (FastAPI) que agrega señales de derivados BTC para Make/HTTP21:
- `funding_rate`, `funding_eta_min`
- `perp_basis_annualized` (premium mark vs index; fracción)
- `oi_change_15m`, `long_short_ratio` (Rubik opcional)
- `nearest_liq_up_pct`, `nearest_liq_dn_pct` (agregado vía WebSocket)
- Referencias: `mark_price`, `index_px`, `ts`

## 1) Instalación local
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8080
# http://localhost:8080/health
# http://localhost:8080/btc-derivs?instId=BTC-USDT-SWAP&indexId=BTC-USDT&ccy=BTC&period=15m
```

## 2) Docker
```bash
docker build -t tia-derivs-bridge:latest .
docker run --rm -p 8080:8080 --env-file .env tia-derivs-bridge:latest
```

## 3) Deploy en Render (opcional)
Crea un nuevo Web Service apuntando a este repo. Comando de inicio:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 4) Endpoint principal
`GET /btc-derivs?instId=BTC-USDT-SWAP&indexId=BTC-USDT&ccy=BTC&period=15m`

Respuesta:
```json
{
  "derivs": {
    "funding_rate": 0.0001,
    "funding_eta_min": 124,
    "perp_basis_annualized": 0.08,
    "oi_change_15m": -1.9,
    "long_short_ratio": 1.12,
    "nearest_liq_up_pct": 0.0028,
    "nearest_liq_dn_pct": 0.0035
  },
  "market_refs": {
    "mark_price": 120047.55,
    "index_px": 119980.12,
    "ts": 1723488000000
  }
}
```

## 5) Uso en Make (HTTP 21)
Mapea:
- `{{21.data.derivs.funding_rate}}`
- `{{21.data.derivs.funding_eta_min}}`
- `{{21.data.derivs.perp_basis_annualized}}`
- `{{21.data.derivs.oi_change_15m}}`
- `{{21.data.derivs.long_short_ratio}}`
- `{{21.data.derivs.nearest_liq_up_pct}}`
- `{{21.data.derivs.nearest_liq_dn_pct}}`

## 6) Notas
- `USE_RUBIK=1` activa endpoints de Trading Data (mejor para OI/long-short).
- Los clústers de liquidación necesitan ~30–120s de calentamiento tras iniciar.
- `CACHE_TTL` controla el caché simple de consultas REST.
