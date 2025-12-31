from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from polymarketbot.config import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    token_id: str
    price: Optional[float]
    size: int
    order_type: str = "market"


class Executor:
    """Submit orders in live or dry-run mode."""

    def __init__(self, clob_client, risk: RiskConfig, live: bool = False) -> None:
        self.clob_client = clob_client
        self.risk = risk
        self.live = live
        self.daily_trades = 0

    def _check_kill_switch(self) -> None:
        if self.risk.kill_switch_file_path.exists():
            logger.error("Kill switch file found (%s); aborting orders", self.risk.kill_switch_file_path)
            try:
                self.clob_client.cancel_all()
            except Exception:
                logger.warning("Cancel-all failed during kill switch")
            raise RuntimeError("Kill switch engaged")

    def _check_limits(self, request: OrderRequest) -> None:
        if self.daily_trades >= self.risk.max_daily_trades:
            raise RuntimeError("Daily trade limit reached")

    def buy_shares(self, request: OrderRequest) -> Dict[str, str]:
        self._check_kill_switch()
        self._check_limits(request)

        if not self.live:
            logger.info("[DRY-RUN] Buy %s shares of %s at %s (%s)", request.size, request.token_id, request.price, request.order_type)
            self.daily_trades += 1
            return {"status": "dry-run", "token_id": request.token_id}

        try:
            if request.order_type == "market":
                order = self.clob_client.create_market_order(token_id=request.token_id, size=request.size, side="buy")
            else:
                order = self.clob_client.create_order(
                    token_id=request.token_id,
                    price=request.price,
                    size=request.size,
                    side="buy",
                    time_in_force="IOC",
                )
            response = self.clob_client.post_order(order)
            self.daily_trades += 1
            return response
        except Exception as exc:  # pragma: no cover - network dependent
            logger.error("Order failed: %s", exc)
            raise
