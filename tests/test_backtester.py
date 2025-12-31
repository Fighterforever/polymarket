import unittest
from pathlib import Path

from polymarketbot.backtest import RecordedBacktester
from polymarketbot.strategy import Snapshot


class BacktesterTests(unittest.TestCase):
    def test_sample_dataset_generates_single_trade(self) -> None:
        dataset = Path("data/sample_snapshots.csv")
        backtester = RecordedBacktester(
            starting_balance=1000.0,
            shares=10,
            sum_target=0.95,
            move_pct=0.15,
            window_minutes=2,
        )
        snapshots = backtester.load_snapshots(dataset)
        result = backtester.run(snapshots)

        self.assertAlmostEqual(result.total_profit, 0.70, places=2)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.round_slug, "round-1")
        self.assertEqual(trade.leg1_side, "up")
        self.assertAlmostEqual(trade.leg1_price, 0.42, places=2)
        self.assertAlmostEqual(trade.leg2_price or 0.0, 0.51, places=2)


if __name__ == "__main__":
    unittest.main()
