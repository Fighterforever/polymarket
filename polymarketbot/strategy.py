from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional, Tuple


@dataclass
class Snapshot:
    """Represents a single best-ask snapshot for both outcomes."""

    timestamp: float
    round_slug: str
    seconds_remaining: int
    up_ask: float
    down_ask: float


@dataclass
class TradeEvent:
    """Captured trades for reporting."""

    round_slug: str
    leg1_side: str
    leg1_price: float
    leg2_price: Optional[float]
    shares: int
    profit: float
    note: str


class TwoLegStrategy:
    """Implements the two-leg capture-and-hedge loop described in the post."""

    def __init__(
        self,
        shares: int,
        sum_target: float = 0.95,
        move_pct: float = 0.15,
        window_minutes: int = 2,
        drop_window_seconds: int = 3,
    ) -> None:
        self.shares = shares
        self.sum_target = sum_target
        self.move_pct = move_pct
        self.window_minutes = window_minutes
        self.drop_window_seconds = drop_window_seconds

    def run_round(self, snapshots: Iterable[Snapshot]) -> Tuple[float, List[TradeEvent]]:
        """Process all snapshots for a single round.

        Returns the profit for the round and the captured trade events.
        """

        events: List[TradeEvent] = []
        history: Dict[str, Deque[Tuple[float, float]]] = {
            "up": deque(),
            "down": deque(),
        }

        leg1_side: Optional[str] = None
        leg1_price: Optional[float] = None
        leg2_price: Optional[float] = None

        snapshots_list = list(snapshots)
        if not snapshots_list:
            return 0.0, events

        round_start = snapshots_list[0].timestamp
        window_limit = round_start + self.window_minutes * 60

        for snap in snapshots_list:
            self._append_price(history, "up", snap.timestamp, snap.up_ask)
            self._append_price(history, "down", snap.timestamp, snap.down_ask)

            if leg1_side is None and snap.timestamp <= window_limit:
                triggered_side = self._detect_drop(history, snap.timestamp)
                if triggered_side:
                    leg1_side = triggered_side
                    leg1_price = snap.up_ask if triggered_side == "up" else snap.down_ask

            if leg1_side and leg2_price is None:
                opposite_side = "down" if leg1_side == "up" else "up"
                opposite_price = snap.down_ask if opposite_side == "down" else snap.up_ask
                if leg1_price is not None and leg1_price + opposite_price <= self.sum_target:
                    leg2_price = opposite_price
                    profit = self._paired_profit(leg1_price, leg2_price)
                    events.append(
                        TradeEvent(
                            round_slug=snap.round_slug,
                            leg1_side=leg1_side,
                            leg1_price=leg1_price,
                            leg2_price=leg2_price,
                            shares=self.shares,
                            profit=profit,
                            note="paired hedge executed",
                        )
                    )
                    return profit, events

        # If we exit the loop without leg2, treat leg1 as full loss.
        if leg1_side and leg1_price is not None:
            loss = -leg1_price * self.shares
            events.append(
                TradeEvent(
                    round_slug=snapshots_list[-1].round_slug,
                    leg1_side=leg1_side,
                    leg1_price=leg1_price,
                    leg2_price=None,
                    shares=self.shares,
                    profit=loss,
                    note="leg2 missed; treated as full loss",
                )
            )
            return loss, events

        return 0.0, events

    def _append_price(
        self, history: Dict[str, Deque[Tuple[float, float]]], side: str, ts: float, price: float
    ) -> None:
        window = history[side]
        window.append((ts, price))
        cutoff = ts - self.drop_window_seconds
        while window and window[0][0] < cutoff:
            window.popleft()

    def _detect_drop(self, history: Dict[str, Deque[Tuple[float, float]]], ts: float) -> Optional[str]:
        for side in ("up", "down"):
            window = history[side]
            if len(window) < 2:
                continue
            oldest_ts, oldest_price = window[0]
            latest_ts, latest_price = window[-1]
            # The deque only keeps prices within `drop_window_seconds`, so we can
            # directly measure the drop between the earliest and latest points in
            # that rolling window (i.e., any fall that happens within ~N seconds).
            if oldest_price <= 0:
                continue
            drop = (oldest_price - latest_price) / oldest_price
            if drop >= self.move_pct:
                return side
        return None

    def _paired_profit(self, leg1_price: float, leg2_price: float) -> float:
        total_cost = (leg1_price + leg2_price) * self.shares
        payout = 1.0 * self.shares
        return payout - total_cost
