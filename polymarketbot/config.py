from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseSettings, Field, validator


load_dotenv()


class Settings(BaseSettings):
    """Runtime configuration for the live trading bot.

    Environment variables take precedence over values loaded from a .env file.
    The defaults keep the bot in safe dry-run mode unless explicitly overridden.
    """

    # Network
    clob_host: str = Field("https://clob.polymarket.com", env="CLOB_HOST")
    chain_id: int = Field(137, env="CHAIN_ID")

    # Authentication
    private_key: Optional[str] = Field(default=None, env="PRIVATE_KEY")
    funder: Optional[str] = Field(default=None, env="FUNDER")
    signature_type: Optional[str] = Field(default=None, env="SIGNATURE_TYPE")
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    secret: Optional[str] = Field(default=None, env="SECRET")
    passphrase: Optional[str] = Field(default=None, env="PASSPHRASE")

    # Market discovery
    market_identifier: Optional[str] = Field(default=None)
    token_ids: List[str] = Field(default_factory=list)

    # Trading parameters
    shares: int = Field(10)
    notional_usd: Optional[float] = Field(default=None)
    order_type: str = Field("market")  # market or limit
    move_pct: float = Field(0.15)
    drop_window_seconds: int = Field(3)
    sum_target: float = Field(0.95)
    window_minutes: int = Field(2)

    # Risk controls
    max_position_usd: float = Field(200.0)
    max_daily_trades: int = Field(20)
    max_slippage: float = Field(0.05)
    kill_switch_file_path: Path = Field(Path(".polymarketbot_kill"))
    enable_live_trading: bool = Field(False)

    # Strategy flags
    allow_incomplete_hedge: bool = Field(False)
    hedge_timeout_seconds: int = Field(60)
    allow_concurrent_trades: bool = Field(False)

    log_path: Path = Field(Path("logs/polymarketbot.log"))
    state_path: Path = Field(Path("data/state.sqlite"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("order_type")
    def validate_order_type(cls, value: str) -> str:
        if value not in {"market", "limit"}:
            raise ValueError("order_type must be 'market' or 'limit'")
        return value

    @property
    def live_trading_enabled(self) -> bool:
        env_flag = os.getenv("LIVE_TRADING", "0") == "1"
        return bool(self.enable_live_trading and env_flag)


@dataclass
class MarketConfig:
    """Resolved market configuration after discovery."""

    market_identifier: str
    yes_token_id: str
    no_token_id: str
    shares: int
    sum_target: float
    move_pct: float
    drop_window_seconds: int
    window_minutes: int
    allow_concurrent_trades: bool = False
    allow_incomplete_hedge: bool = False
    hedge_timeout_seconds: int = 60


@dataclass
class RiskConfig:
    max_position_usd: float
    max_daily_trades: int
    max_slippage: float
    kill_switch_file_path: Path
    enable_live_trading: bool = False


def load_settings() -> Settings:
    """Load settings from environment and .env file."""

    return Settings()
