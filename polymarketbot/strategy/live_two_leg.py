from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from polymarketbot.config import MarketConfig
from polymarketbot.execution.executor import Executor, OrderRequest
from polymarketbot.state.store import StateStore

logger = logging.getLogger(__name__)


@dataclass
class LiveStrategyState:
    leg1_token_id: Optional[str] = None
    leg1_price: Optional[float] = None
    leg1_time: Optional[float] = None
    active: bool = False


class LiveTwoLegStrategy:
    """Event-driven version of TwoLegStrategy for live trading."""

    def __init__(
        self,
        market: MarketConfig,
        executor: Executor,
        store: StateStore,
    ) -> None:
        self.market = market
        self.executor = executor
        self.store = store
        self.history: Dict[str, Deque[tuple[float, float]]] = {
            market.yes_token_id: deque(),
            market.no_token_id: deque(),
        }
        self.state = self.store.load_state() or LiveStrategyState()
        self.round_start: Optional[float] = None

    def _append_price(self, token_id: str, ts: float, price: float) -> None:
        window = self.history[token_id]
        window.append((ts, price))
        cutoff = ts - self.market.drop_window_seconds
        while window and window[0][0] < cutoff:
            window.popleft()

    def _detect_drop(self, token_id: str) -> bool:
        window = self.history[token_id]
        if len(window) < 2:
            return False
        oldest_ts, oldest_price = window[0]
        latest_ts, latest_price = window[-1]
        if oldest_price <= 0:
            return False
        drop = (oldest_price - latest_price) / oldest_price
        return drop >= self.market.move_pct

    def _within_window(self, ts: float) -> bool:
        if self.round_start is None:
            self.round_start = ts
        return ts <= self.round_start + self.market.window_minutes * 60

    def handle_price(self, token_id: str, price: float, ts: Optional[float] = None) -> None:
        ts = ts or time.time()
        if token_id not in self.history:
            return
        self._append_price(token_id, ts, price)
        if not self.state.active and not self.market.allow_concurrent_trades:
            if self.state.leg1_token_id:
                return
        if not self._within_window(ts):
            return

        if self.state.leg1_token_id is None and self._detect_drop(token_id):
            self._open_leg1(token_id, price, ts)
            return

        if self.state.leg1_token_id and token_id != self.state.leg1_token_id:
            self._try_leg2(token_id, price, ts)

    def _open_leg1(self, token_id: str, price: float, ts: float) -> None:
        self.state = LiveStrategyState(
            leg1_token_id=token_id, leg1_price=price, leg1_time=ts, active=True
        )
        self.store.save_state(self.state)
        logger.info("Leg1 triggered on %s at %.4f", token_id, price)
        self.executor.buy_shares(
            OrderRequest(token_id=token_id, price=price, size=self.market.shares)
        )

    def _try_leg2(self, token_id: str, price: float, ts: float) -> None:
        if not self.state.leg1_price:
            return
        if self.state.leg1_price + price <= self.market.sum_target:
            logger.info(
                "Leg2 executing on %s at %.4f after leg1 %s",
                token_id,
                price,
                self.state.leg1_token_id,
            )
            self.executor.buy_shares(
                OrderRequest(token_id=token_id, price=price, size=self.market.shares)
            )
            self.store.record_event(
                {
                    "type": "hedged",
                    "leg1": self.state.leg1_token_id,
                    "leg1_price": self.state.leg1_price,
                    "leg2": token_id,
                    "leg2_price": price,
                    "timestamp": ts,
                }
            )
            self.state = LiveStrategyState()
            self.store.save_state(self.state)
            return

        if self.state.leg1_time and (ts - self.state.leg1_time) > self.market.hedge_timeout_seconds:
            self.store.record_event(
                {
                    "type": "hedge_timeout",
                    "leg1": self.state.leg1_token_id,
                    "timestamp": ts,
                }
            )
            if not self.market.allow_incomplete_hedge:
                logger.warning("Hedge timeout reached; keeping position and alerting only")
            self.state.active = False
            self.store.save_state(self.state)
