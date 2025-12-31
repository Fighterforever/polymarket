import tempfile
import unittest
import os
from pathlib import Path

from polymarketbot.config import MarketConfig, RiskConfig
from polymarketbot.execution.executor import Executor, OrderRequest
from polymarketbot.state.store import StateStore
from polymarketbot.strategy.live_two_leg import LiveTwoLegStrategy


class DummyClob:
    def cancel_all(self):
        return {}

    def create_market_order(self, **kwargs):
        return {"order": kwargs}

    def post_order(self, order):
        return {"posted": order}


class RecordingExecutor(Executor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orders = []

    def buy_shares(self, request: OrderRequest):  # type: ignore[override]
        self.orders.append(request)
        return super().buy_shares(request)


class LiveStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "state.sqlite"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_strategy_executes_two_legs_on_feed(self) -> None:
        market = MarketConfig(
            market_identifier="test",
            yes_token_id="yes",
            no_token_id="no",
            shares=5,
            sum_target=0.90,
            move_pct=0.1,
            drop_window_seconds=3,
            window_minutes=2,
            allow_concurrent_trades=False,
            allow_incomplete_hedge=False,
            hedge_timeout_seconds=30,
        )
        risk = RiskConfig(
            max_position_usd=100,
            max_daily_trades=10,
            max_slippage=0.05,
            kill_switch_file_path=Path(self.tmpdir.name) / "kill",
            enable_live_trading=False,
        )
        clob = DummyClob()
        executor = RecordingExecutor(clob_client=clob, risk=risk, live=False)
        store = StateStore(self.state_path)
        strat = LiveTwoLegStrategy(market=market, executor=executor, store=store)

        strat.handle_price("yes", 0.60, ts=0)
        strat.handle_price("yes", 0.54, ts=1)
        strat.handle_price("yes", 0.48, ts=2)  # drop > 0.1 triggers leg1
        strat.handle_price("no", 0.42, ts=2.1)  # sum 0.9 triggers leg2

        self.assertEqual(len(executor.orders), 2)
        self.assertEqual(executor.orders[0].token_id, "yes")
        self.assertEqual(executor.orders[1].token_id, "no")


if __name__ == "__main__":
    unittest.main()
