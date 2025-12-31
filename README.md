# Polymarket two-leg bot (backtest + live dry-run)

This repository contains both the original backtesting tools and a **safe-by-default** live trading harness for Polymarket's CLOB. The live bot streams best-ask updates for a binary market, waits for a sharp drop on one side (Leg 1), and immediately hedges with the opposite side (Leg 2) when the combined entry cost is below a configurable threshold.

- Default mode is **dry-run**; no orders are sent unless `enable_live_trading=True` _and_ `LIVE_TRADING=1` are set.
- Rate limits: keep Gamma/Data API queries below official limits (this project uses websocket market data and minimal polling). Be polite with retries and exponential backoff when extending.
- Secrets: never log your private key, secret, or passphrase.

## Layout

- `polymarketbot/config.py` — Pydantic settings for env-driven config and risk controls.
- `polymarketbot/clients/` — wrappers for Polymarket CLOB (py-clob-client) and Gamma discovery APIs.
- `polymarketbot/marketdata/wss_market.py` — websocket subscription with reconnect + best-ask cache.
- `polymarketbot/execution/executor.py` — dry-run/live order executor with kill-switch and limits.
- `polymarketbot/strategy/` — backtest (`base.py`) and live streaming (`live_two_leg.py`) strategies.
- `polymarketbot/state/store.py` — SQLite persistence for bot state and events.
- `polymarketbot/cli.py` — original backtest CLI.
- `polymarketbot/cli_live.py` — live runner: `run`, `cancel-all`, `status`, `print-config`.
- `scripts/setup_allowances.py` — optional placeholder for ERC20 approvals (inert unless edited and run).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment & .env

Create a `.env` in the repo root (values are optional unless you enable live trading):

```
CLOB_HOST=https://clob.polymarket.com
CHAIN_ID=137
PRIVATE_KEY=0x...
FUNDER=0x...
SIGNATURE_TYPE=eip712
API_KEY= # optional if PRIVATE_KEY provided
SECRET=
PASSPHRASE=
LIVE_TRADING=0
```

Two authentication paths:
- Provide `PRIVATE_KEY` and the wrapper will derive/cache L2 API credentials (saved to `.polymarket_api_creds.json`, chmod 600).
- Or provide `API_KEY/SECRET/PASSPHRASE` directly to skip derivation.

## Running (dry-run)

```bash
python -m polymarketbot.cli_live run --market "btc"  # searches Gamma for the market, dry-run only
```

- The bot resolves token IDs via Gamma, subscribes to the CLOB websocket, and logs intended orders without posting.
- Kill-switch: if the file at `kill_switch_file_path` exists (default `.polymarketbot_kill`), the bot cancels open orders (if any) and exits.

## Enabling live trading (dangerous)

1. Set `enable_live_trading=True` in your environment or `.env` (Pydantic setting).
2. Set `LIVE_TRADING=1` as an explicit on-switch.
3. Fund your wallet, configure allowances (see `scripts/setup_allowances.py` placeholder), and test on dry-run first.

Only when both flags are set will the executor post orders. Market orders (default) or IOC limit orders are used to avoid resting orders; adjust `max_slippage` and `max_position_usd` in config to suit your risk.

## Strategy parameters

- `move_pct`: required drop within `drop_window_seconds` to trigger Leg 1 (best-ask based).
- `sum_target`: execute Leg 2 when `leg1_price + opposite_best_ask <= sum_target`.
- `window_minutes`: after this window, Leg 1 will no longer trigger.
- `allow_incomplete_hedge`: if False (default), Leg 2 timeouts only log/alert and do not auto-sell.
- `hedge_timeout_seconds`: time allowed after Leg 1 before triggering the timeout handler.
- `allow_concurrent_trades`: keep a single active trade per market by default.

## Risk controls

- `max_position_usd`, `max_daily_trades`, `max_slippage` (enforced in executor where applicable).
- Kill switch file check before every order.
- Dry-run default to prevent accidental execution.

## Tests

```bash
python -m unittest discover -s tests
```

Includes backtest sanity checks, live strategy event simulation, and executor dry-run safety.

## Limitations & notes

- Websocket reconnect/backoff is implemented, but you should add monitoring and alerting before real deployment.
- No GUI is provided; consider adding Prometheus or structured log aggregation.
- Respect Polymarket/Gamma rate limits; throttle additional REST calls if you extend data fetching.

## Example commands

- Backtest: `python -m polymarketbot.cli data/sample_snapshots.csv`
- Live dry-run: `python -m polymarketbot.cli_live run --market "btc"`
- Cancel open orders: `python -m polymarketbot.cli_live cancel-all`
- Inspect stored state: `python -m polymarketbot.cli_live status`

## Disclaimer

This code is provided for educational purposes. Trading involves significant risk. Use dry-run mode and small size in testing; you are responsible for safeguarding your keys and funds.
