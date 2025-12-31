import tempfile
import unittest
from pathlib import Path

from polymarketbot.config import RiskConfig
from polymarketbot.execution.executor import Executor, OrderRequest


class DummyClob:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel_all(self):
        self.cancelled = True
        return {}

    def create_market_order(self, **kwargs):
        return {"order": kwargs}

    def post_order(self, order):
        return {"posted": order}


class ExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.kill_switch = Path(self.tmpdir.name) / "kill"
        self.risk = RiskConfig(
            max_position_usd=100,
            max_daily_trades=3,
            max_slippage=0.05,
            kill_switch_file_path=self.kill_switch,
            enable_live_trading=False,
        )
        self.clob = DummyClob()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_dry_run_records_without_posting(self) -> None:
        executor = Executor(clob_client=self.clob, risk=self.risk, live=False)
        result = executor.buy_shares(OrderRequest(token_id="yes", price=0.5, size=1))
        self.assertEqual(result.get("status"), "dry-run")
        self.assertFalse(self.clob.cancelled)

    def test_kill_switch_blocks_orders(self) -> None:
        self.kill_switch.write_text("stop")
        executor = Executor(clob_client=self.clob, risk=self.risk, live=False)
        with self.assertRaises(RuntimeError):
            executor.buy_shares(OrderRequest(token_id="yes", price=0.5, size=1))
        self.assertTrue(self.clob.cancelled)


if __name__ == "__main__":
    unittest.main()
