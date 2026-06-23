# Samsung Electronics Auto-Trader

A modular Python auto-trading program for **Samsung Electronics (005930)**
using the [Korea Investment & Securities Open API](https://apiportal.koreainvestment.com/)
in the **mock (paper) trading environment**.

---

## Folder Structure

```
samsung_auto_trader/
├── main.py           # Entry point – run this file
├── config.py         # Constants, offsets, and credential loading
├── logger.py         # Centralised logging setup
├── auth.py           # Token issuance + same-day file cache
├── api_client.py     # Low-level HTTP GET/POST with retry logic
├── market_data.py    # Fetch current price for 005930
├── account.py        # Query holdings and available cash
├── orders.py         # Place buy / sell (limit) orders
├── trader.py         # Core trading loop (09:10 – 15:30 KST)
├── token_cache.json  # Auto-generated at runtime – do NOT commit
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | Required for `X \| Y` type-union syntax |
| `requests` library | `pip install requests` or `uv add requests` |
| Korea Investment mock-trading account | [How to apply](https://apiportal.koreainvestment.com/about-howto) |

---

## Environment Variables

Set these **before** running the program.  They must never be hard-coded.

| Variable | Description | Example |
|---|---|---|
| `GH_ACCOUNT` | Account number (8-digit + 2-digit) | `1234567801` or `12345678-01` |
| `GH_APPKEY` | Mock-trading App Key | `PSxxxxxxxxxxxxxxxx` |
| `GH_APPSECRET` | Mock-trading App Secret | `xxxxxxxxxxxxxxxxx…` |

### Setting variables on Linux / macOS

```bash
export GH_ACCOUNT="1234567801"
export GH_APPKEY="PSxxxxxxxxxxxxxxxx"
export GH_APPSECRET="xxxxxxxxxx…"
```

### Setting variables on Windows (PowerShell)

```powershell
$env:GH_ACCOUNT   = "1234567801"
$env:GH_APPKEY    = "PSxxxxxxxxxxxxxxxx"
$env:GH_APPSECRET = "xxxxxxxxxx…"
```

### VS Code: using a `.env` file (recommended)

Create a file named `.env` **inside `samsung_auto_trader/`** (it is already
gitignored):

```env
GH_ACCOUNT=1234567801
GH_APPKEY=PSxxxxxxxxxxxxxxxx
GH_APPSECRET=xxxxxxxxxx…
```

Then in `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run Samsung Auto-Trader (mock)",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/samsung_auto_trader/main.py",
      "envFile": "${workspaceFolder}/samsung_auto_trader/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Installation

```bash
# From the repo root
pip install -r samsung_auto_trader/requirements.txt

# Or with uv (recommended)
uv pip install -r samsung_auto_trader/requirements.txt
```

---

## Running

```bash
# From inside the samsung_auto_trader/ folder
cd samsung_auto_trader

# Mock trading (default – safe)
python main.py

# More verbose logging
python main.py --log-level DEBUG

# Real trading ⚠  only after thorough mock testing
python main.py --real
```

---

## Trading Logic

Each cycle (every `POLL_INTERVAL_SECONDS = 60 s` inside the trading window):

1. **Fetch current price** of 005930.
2. **Read holdings / cash** (logged as "Before").
3. **Submit limit BUY** at `current_price - 1 000 KRW`.
4. **Submit limit SELL** at `current_price + 1 000 KRW`.
5. **Re-read holdings / cash** (logged as "After").
6. **Log execution check** – compares qty before vs after.

The program only runs between **09:10 and 15:30 (KST / local system time)**.
It exits automatically at market close.

Each cycle makes approximately **5 API calls**:
- 1 × current price fetch
- 1 × account balance query (before orders)
- 1 × buy order submission
- 1 × sell order submission
- 1 × account balance query (after orders, for execution confirmation)

### Adjusting the spread

Edit `config.py`:

```python
BUY_OFFSET  = 1_000  # KRW below current price
SELL_OFFSET = 1_000  # KRW above current price
ORDER_QTY   = 1      # shares per order
```

---

## Token Caching

On the first run, a new token is issued and saved to `token_cache.json`.
All subsequent runs on the same calendar day reuse the cached token without
making an extra API call.  On a new day the cache is automatically refreshed.

**`token_cache.json` contains a Bearer token – keep it private and do NOT
commit it to version control.**

---

## Rate-Limit Safety

The mock environment enforces strict API-call limits.  The default polling
interval is **60 seconds**, and the program makes at most **~5 API calls per
cycle** (1 price + 2 × balance + 2 × orders).  Do not reduce
`POLL_INTERVAL_SECONDS` below 30 seconds for mock trading.

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | CLI argument parsing; calls `run_trading_loop()` |
| `config.py` | All constants (URLs, TR_IDs, offsets, timing); loads env vars |
| `logger.py` | One-time logging setup; `get_logger()` factory |
| `auth.py` | Issues tokens; reads/writes `token_cache.json` |
| `api_client.py` | `get()` / `post()` wrappers; builds headers; retry logic |
| `market_data.py` | `get_current_price()` → `int` |
| `account.py` | `get_account_info()` → `AccountInfo`; parses holdings + cash |
| `orders.py` | `place_buy_order()` / `place_sell_order()` → `OrderResult` |
| `trader.py` | `run_trading_loop()` and `run_one_cycle()` |

---

## Disclaimer

This software is provided for educational and demonstration purposes only.
Trading involves financial risk.  The authors are not responsible for any
trading losses.  Always test thoroughly in the mock environment before
considering any live trading.
