from __future__ import annotations

import argparse
import logging
import time

from polymarketbot.clients.clob_client import PolymarketCLOBClient
from polymarketbot.clients.gamma_client import GammaClient
from polymarketbot.config import MarketConfig, RiskConfig, Settings, load_settings
from polymarketbot.execution.executor import Executor
from polymarketbot.marketdata.wss_market import WSSMarketData
from polymarketbot.state.store import StateStore
from polymarketbot.strategy.live_two_leg import LiveTwoLegStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def build_market_config(settings: Settings) -> MarketConfig:
    tokens = settings.token_ids
    if not tokens:
        gamma = GammaClient()
        tokens = gamma.resolve_market(settings.market_identifier or "")
    if len(tokens) < 2:
        raise ValueError("A binary market requires two token ids")
    return MarketConfig(
        market_identifier=settings.market_identifier or ",".join(tokens),
        yes_token_id=str(tokens[0]),
        no_token_id=str(tokens[1]),
        shares=settings.shares,
        sum_target=settings.sum_target,
        move_pct=settings.move_pct,
        drop_window_seconds=settings.drop_window_seconds,
        window_minutes=settings.window_minutes,
        allow_concurrent_trades=settings.allow_concurrent_trades,
        allow_incomplete_hedge=settings.allow_incomplete_hedge,
        hedge_timeout_seconds=settings.hedge_timeout_seconds,
    )


def build_executor(settings: Settings) -> Executor:
    risk = RiskConfig(
        max_position_usd=settings.max_position_usd,
        max_daily_trades=settings.max_daily_trades,
        max_slippage=settings.max_slippage,
        kill_switch_file_path=settings.kill_switch_file_path,
        enable_live_trading=settings.live_trading_enabled,
    )
    clob = PolymarketCLOBClient(
        host=settings.clob_host,
        chain_id=settings.chain_id,
        private_key=settings.private_key,
        api_key=settings.api_key,
        secret=settings.secret,
        passphrase=settings.passphrase,
        funder=settings.funder,
        signature_type=settings.signature_type,
    )
    return Executor(clob_client=clob, risk=risk, live=settings.live_trading_enabled)


def cmd_run(args: argparse.Namespace) -> None:
    settings = load_settings()
    if args.market:
        settings.market_identifier = args.market
    market_config = build_market_config(settings)
    store = StateStore(settings.state_path)
    executor = build_executor(settings)
    strategy = LiveTwoLegStrategy(market=market_config, executor=executor, store=store)

    feed = WSSMarketData()
    feed.start([market_config.yes_token_id, market_config.no_token_id])
    logger.info("Started websocket feed for %s", market_config.market_identifier)
    try:
        while True:
            for token_id in (market_config.yes_token_id, market_config.no_token_id):
                entry = feed.latest_best_ask.get(token_id)
                if entry:
                    strategy.handle_price(token_id, entry["price"], entry["timestamp"])
            if settings.kill_switch_file_path.exists():
                raise SystemExit("Kill switch triggered")
            time.sleep(0.25)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        feed.stop()


def cmd_cancel_all(args: argparse.Namespace) -> None:
    settings = load_settings()
    executor = build_executor(settings)
    logger.info("Sending cancel_all")
    executor.clob_client.cancel_all()


def cmd_status(args: argparse.Namespace) -> None:
    settings = load_settings()
    store = StateStore(settings.state_path)
    state = store.load_state()
    print("State:", state)


def cmd_print_config(args: argparse.Namespace) -> None:
    settings = load_settings()
    print(settings.json())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Polymarket live trading bot (two-leg hedge)")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run streaming strategy")
    run_p.add_argument("--market", help="condition_id or query", required=False)
    run_p.set_defaults(func=cmd_run)

    cancel_p = sub.add_parser("cancel-all", help="Cancel all open orders")
    cancel_p.set_defaults(func=cmd_cancel_all)

    status_p = sub.add_parser("status", help="Show stored state")
    status_p.set_defaults(func=cmd_status)

    cfg_p = sub.add_parser("print-config", help="Print merged configuration")
    cfg_p.set_defaults(func=cmd_print_config)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
