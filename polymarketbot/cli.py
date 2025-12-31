from __future__ import annotations

import argparse
from pathlib import Path

from .backtest import RecordedBacktester


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay recorded Polymarket snapshots against the two-leg bot.")
    parser.add_argument("snapshot_file", type=Path, help="CSV file containing snapshots.")
    parser.add_argument("--starting-balance", type=float, default=1000.0, help="Starting bankroll in USD.")
    parser.add_argument("--shares", type=int, default=20, help="Order size in shares per leg.")
    parser.add_argument("--sum-target", type=float, default=0.95, help="Threshold for leg1 + leg2 price to trigger hedge.")
    parser.add_argument("--move-pct", type=float, default=0.15, help="Drop percentage over ~3s required to open leg1.")
    parser.add_argument("--window-min", type=int, default=2, help="Minutes after round start where leg1 may trigger.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backtester = RecordedBacktester(
        starting_balance=args.starting_balance,
        shares=args.shares,
        sum_target=args.sum_target,
        move_pct=args.move_pct,
        window_minutes=args.window_min,
    )
    snapshots = backtester.load_snapshots(args.snapshot_file)
    result = backtester.run(snapshots)

    print("Starting balance: $%.2f" % result.starting_balance)
    print("Ending balance  : $%.2f" % result.ending_balance)
    print("Total profit    : $%.2f" % result.total_profit)
    print("ROI             : %.2f%%" % result.roi_pct)
    print("\nTrade log:")
    if not result.trades:
        print("  (no trades executed)")
    for event in result.trades:
        leg2_info = f", leg2={event.leg2_price:.4f}" if event.leg2_price is not None else ", leg2=missed"
        print(
            f"  round={event.round_slug} side={event.leg1_side} leg1={event.leg1_price:.4f}" +
            f"{leg2_info} shares={event.shares} profit={event.profit:.2f} note={event.note}"
        )


if __name__ == "__main__":
    main()
