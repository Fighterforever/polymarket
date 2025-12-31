# Polymarket two-leg bot backtester

Deterministic replay engine for the two-leg Polymarket strategy described in @the_smart_ape's thread (BTC 15-minute UP/DOWN). It focuses on capturing a sharp drop (Leg 1) and hedging when both sides are sufficiently cheap (Leg 2), using recorded best-ask snapshots instead of live trading.

The goal is to make the logic transparent, tunable, and reproducible for parameter sweeps before wiring real trading APIs.

## Quick start

### Run the sample backtest

```bash
python -m polymarketbot.cli data/sample_snapshots.csv --shares 10 --sum-target 0.95 --move-pct 0.15 --window-min 2
```

Expected output (sample dataset executes one paired trade):

```
Starting balance: $1000.00
Ending balance  : $1000.70
Total profit    : $0.70
ROI             : 0.07%

Trade log:
  round=round-1 side=up leg1=0.4200, leg2=0.5100 shares=10 profit=0.70 note=paired hedge executed
```

### Run tests

```bash
python -m unittest discover -s tests
```

## Strategy recap

- **Market context**: BTC 15-minute UP/DOWN market (binary outcome). A temporary mispricing often appears during violent moves.
- **Leg 1 – drop capture**: In the opening window (default 2 minutes), watch for ≥`move_pct` price drop within `drop_window_seconds` (default 3s) on either side. Buy that side at best ask.
- **Leg 2 – hedge trigger**: After Leg 1, continuously monitor the opposite side. When `leg1_price + opposite_ask ≤ sum_target`, buy the opposite side to lock in payout spread.
- **Round rollovers**: Each set of snapshots represents a round. If the round ends before Leg 2 fires, Leg 1 is treated as a full loss (conservative worst-case assumption).

## Parameters and how to tune

| Flag | Meaning | Typical starting point |
| --- | --- | --- |
| `--shares` | Order size per leg (shares) | 10–50 depending on bankroll |
| `--sum-target` | Max combined entry cost for Leg1 + Leg2 | 0.95 (conservative) |
| `--move-pct` | Drop percentage within ~3s to open Leg1 | 0.15 for sharp moves; 0.01 is aggressive |
| `--window-min` | Minutes after round start when Leg1 may trigger | 2 for open-volatility focus |
| `drop_window_seconds` | Rolling window for drop detection (fixed to 3s in CLI; configurable in code) | 3 |

Tuning advice (mirrors the thread):
- Conservative: higher `sum_target` (e.g., 0.95), higher `move_pct` (0.15), short `window_min` (2). Produced ~+86% ROI in the author’s recorded run (with conservative fees/spread assumptions).
- Aggressive: lower `sum_target` (0.6), tiny `move_pct` (0.01), long `window_min` (15). Led to ~-50% ROI in a couple of days—parameter choice is decisive.

## Snapshot format

CSV headers (see `data/sample_snapshots.csv`):

- `timestamp`: floating seconds (monotonic within a round; can be epoch or relative).
- `round_slug`: unique ID per 15-minute round.
- `seconds_remaining`: seconds left in the round at capture time (informational only).
- `up_ask` / `down_ask`: best ask prices for the Up and Down contracts.

Snapshots should be sorted by `(round_slug, timestamp)`. The loader sorts defensively, but pre-sorting helps reproducibility on large files.

## File map

- `polymarketbot/strategy.py` — two-leg loop with drop detection and hedge trigger.
- `polymarketbot/backtest.py` — snapshot replay and ROI accounting per round.
- `polymarketbot/cli.py` — CLI entrypoint for running backtests and printing trade logs.
- `data/sample_snapshots.csv` — tiny dataset that executes one paired trade for demonstration.
- `tests/test_backtester.py` — sanity check for the sample dataset output.

## What this backtester **does not** model (yet)

- Order book depth, partial fills, or volume constraints.
- Latency, network jitter, queueing, or API rate limits.
- Maker/taker fee tiers or dynamic fees; assumes deterministic fills at best ask.
- Market impact of your own orders and adversarial bots reacting to your flow.
- Sub-second microstructure; snapshots are typically ~1s cadence.

These gaps mirror the caveats noted in the original thread. Treat the results as directional for parameter exploration, not as production PnL predictions.

## Suggested optimizations / next steps

- Add a recorder that persists websocket best-bid/ask to CSV/Parquet to build richer datasets.
- Parameter grid search: sweep `sum_target`, `move_pct`, `window_min`, and position sizing to find stable regions.
- Simulate slippage/fees: plug in fee models and book depth to stress-test thin markets.
- Engineering hardening: timeouts, retries, rate-limit handling, and round rollover awareness when streaming live data.
- Performance: port latency-sensitive pieces to Rust and/or place the service near Polymarket infra, as suggested in the source thread.

## Disclaimer

This repository is for research and parameter exploration only. Nothing here constitutes financial advice. Real-money trading on Polymarket (or any venue) carries significant risk.
