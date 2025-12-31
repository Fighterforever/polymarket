from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON
except Exception as exc:  # pragma: no cover - import guard for environments without dependency
    ClobClient = None  # type: ignore
    POLYGON = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class ApiCredentials:
    api_key: str
    secret: str
    passphrase: str

    def to_json(self) -> str:
        return json.dumps({
            "api_key": self.api_key,
            "secret": self.secret,
            "passphrase": self.passphrase,
        })

    @classmethod
    def from_json(cls, payload: str) -> "ApiCredentials":
        data = json.loads(payload)
        return cls(
            api_key=data["api_key"],
            secret=data["secret"],
            passphrase=data["passphrase"],
        )


class PolymarketCLOBClient:
    """Wrapper around py-clob-client with credential bootstrap and safe logging."""

    def __init__(
        self,
        host: str,
        chain_id: int,
        private_key: Optional[str] = None,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        funder: Optional[str] = None,
        signature_type: Optional[str] = None,
        credentials_cache: Path = Path(".polymarket_api_creds.json"),
    ) -> None:
        if ClobClient is None:
            raise RuntimeError("py-clob-client is required but not installed")

        self.host = host
        self.chain_id = chain_id
        self.credentials_cache = credentials_cache
        self.private_key = private_key
        self.funder = funder
        self.signature_type = signature_type

        self.creds = self._load_or_create_credentials(api_key, secret, passphrase)
        self.client = ClobClient(
            host=self.host,
            chain_id=self.chain_id,
            key=self.private_key,
            api_creds={
                "apiKey": self.creds.api_key,
                "secret": self.creds.secret,
                "passphrase": self.creds.passphrase,
            },
            funder=self.funder,
            signature_type=self.signature_type,
        )

    def _load_or_create_credentials(
        self, api_key: Optional[str], secret: Optional[str], passphrase: Optional[str]
    ) -> ApiCredentials:
        if api_key and secret and passphrase:
            return ApiCredentials(api_key=api_key, secret=secret, passphrase=passphrase)

        if self.private_key:
            cached = self._load_cached_credentials()
            if cached:
                return cached

            logger.info("Generating L2 API credentials from private key (will be cached)")
            creds = self._derive_api_credentials()
            self._cache_credentials(creds)
            return creds

        raise ValueError("Either API credentials or PRIVATE_KEY must be provided")

    def _derive_api_credentials(self) -> ApiCredentials:
        if not self.private_key:
            raise ValueError("private_key required to derive credentials")

        try:
            # py-clob-client provides a helper to create or derive API credentials
            raw = ClobClient.create_or_derive_api_creds(self.private_key)
            return ApiCredentials(
                api_key=raw["apiKey"],
                secret=raw["secret"],
                passphrase=raw["passphrase"],
            )
        except Exception as exc:  # pragma: no cover - passthrough from library
            logger.error("Failed to derive API credentials: %s", exc)
            raise

    def _load_cached_credentials(self) -> Optional[ApiCredentials]:
        if self.credentials_cache.exists():
            try:
                payload = self.credentials_cache.read_text()
                return ApiCredentials.from_json(payload)
            except Exception:
                logger.warning("Failed to read cached API credentials; regenerating")
        return None

    def _cache_credentials(self, creds: ApiCredentials) -> None:
        try:
            self.credentials_cache.write_text(creds.to_json())
            self.credentials_cache.chmod(0o600)
        except Exception:
            logger.warning("Could not cache API credentials; please store them securely")

    # --- Trading helpers ---
    def get_order_book(self, token_id: str) -> Dict[str, Any]:
        return self.client.get_order_book(token_id)

    def get_price(self, token_id: str) -> Optional[float]:
        book = self.get_order_book(token_id)
        asks = book.get("asks") or []
        if not asks:
            return None
        return float(asks[0]["price"])

    def get_midpoint(self, token_id: str) -> Optional[float]:
        book = self.get_order_book(token_id)
        asks = book.get("asks") or []
        bids = book.get("bids") or []
        if not asks or not bids:
            return None
        return (float(asks[0]["price"]) + float(bids[0]["price"])) / 2

    def create_order(self, **kwargs: Any) -> Dict[str, Any]:
        return self.client.create_order(**kwargs)

    def create_market_order(self, **kwargs: Any) -> Dict[str, Any]:
        return self.client.create_market_order(**kwargs)

    def post_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post_order(order)

    def cancel(self, order_id: str) -> Dict[str, Any]:
        return self.client.cancel(order_id)

    def cancel_all(self) -> Dict[str, Any]:
        return self.client.cancel_all()

    def get_balances(self) -> Dict[str, Any]:  # pragma: no cover - passthrough
        if hasattr(self.client, "get_balances"):
            return self.client.get_balances()
        raise NotImplementedError("Balance endpoint not available in client version")
