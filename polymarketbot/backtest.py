from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .strategy import Snapshot, TradeEvent, TwoLegStrategy


@dataclass
class BacktestResult:
    total_profit: float
    starting_balance: float
    ending_balance: float
    roi_pct: float
    trades: List[TradeEvent]


class RecordedBacktester:
    """Replay recorded best-ask snapshots through the two-leg strategy."""

    def __init__(
        self,
        starting_balance: float,
        shares: int,
        sum_target: float = 0.95,
        move_pct: float = 0.15,
        window_minutes: int = 2,
    ) -> None:
        self.strategy = TwoLegStrategy(
            shares=shares,
            sum_target=sum_target,
            move_pct=move_pct,
            window_minutes=window_minutes,
        )
        self.starting_balance = starting_balance

    def load_snapshots(self, path: Path) -> List[Snapshot]:
        snapshots: List[Snapshot] = []
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                snapshots.append(
                    Snapshot(
                        timestamp=float(row["timestamp"]),
                        round_slug=row["round_slug"],
                        seconds_remaining=int(row["seconds_remaining"]),
                        up_ask=float(row["up_ask"]),
                        down_ask=float(row["down_ask"]),
                    )
                )
        snapshots.sort(key=lambda s: (s.round_slug, s.timestamp))
        return snapshots

    def _group_by_round(self, snapshots: Iterable[Snapshot]) -> Dict[str, List[Snapshot]]:
        grouped: Dict[str, List[Snapshot]] = {}
        for snap in snapshots:
            grouped.setdefault(snap.round_slug, []).append(snap)
        return grouped

    def run(self, snapshots: Iterable[Snapshot]) -> BacktestResult:
        grouped = self._group_by_round(snapshots)
        balance = self.starting_balance
        all_trades: List[TradeEvent] = []

        for round_slug, snaps in grouped.items():
            profit, events = self.strategy.run_round(snaps)
            balance += profit
            all_trades.extend(events)

        roi_pct = ((balance - self.starting_balance) / self.starting_balance) * 100
        return BacktestResult(
            total_profit=balance - self.starting_balance,
            starting_balance=self.starting_balance,
            ending_balance=balance,
            roi_pct=roi_pct,
            trades=all_trades,
        )
