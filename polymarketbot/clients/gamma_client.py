from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    """Lightweight wrapper to discover markets and token IDs."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=self.timeout)

    def search_markets(self, query: str) -> List[Dict[str, Any]]:
        resp = self.client.get(f"{self.base_url}/markets", params={"search": query})
        resp.raise_for_status()
        return resp.json().get("markets", [])

    def get_market_by_condition_id(self, condition_id: str) -> Optional[Dict[str, Any]]:
        resp = self.client.get(f"{self.base_url}/markets/{condition_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def extract_token_ids(self, market: Dict[str, Any]) -> List[str]:
        token_ids = []
        for outcome in market.get("outcomeTokens", []):
            token_id = outcome.get("token_id") or outcome.get("tokenId")
            if token_id:
                token_ids.append(str(token_id))
        return token_ids

    def resolve_market(self, identifier: str) -> List[str]:
        """Resolve token IDs from condition_id or search query."""

        if not identifier:
            raise ValueError("market identifier is required")

        market = self.get_market_by_condition_id(identifier)
        if market:
            tokens = self.extract_token_ids(market)
            if tokens:
                return tokens

        search_results = self.search_markets(identifier)
        if not search_results:
            raise ValueError(f"No markets found for query: {identifier}")
        tokens = self.extract_token_ids(search_results[0])
        if not tokens:
            raise ValueError("Could not extract token ids from market")
        return tokens

    def close(self) -> None:  # pragma: no cover - convenience
        self.client.close()
