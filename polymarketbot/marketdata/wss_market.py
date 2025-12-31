from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from asyncio import AbstractEventLoop
from typing import Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)

WS_ENDPOINT = "wss://clob.polymarket.com/ws"


class WSSMarketData:
    """Maintain latest best asks via the Polymarket CLOB websocket feed."""

    def __init__(self, endpoint: str = WS_ENDPOINT, reconnect_backoff: float = 1.0) -> None:
        self.endpoint = endpoint
        self.reconnect_backoff = reconnect_backoff
        self.latest_best_ask: Dict[str, Dict[str, float]] = {}
        self._loop: Optional[AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._subscriptions: List[str] = []
        self._stop_event = threading.Event()

    def start(self, asset_ids: List[str]) -> None:
        self._subscriptions = list(asset_ids)
        self._stop_event.clear()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        assert self._loop
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    async def _connect(self) -> None:
        backoff = self.reconnect_backoff
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.endpoint, ping_interval=20) as ws:
                    await self._subscribe(ws, self._subscriptions)
                    backoff = self.reconnect_backoff
                    async for message in ws:
                        self._handle_message(message)
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Websocket connection lost: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol, asset_ids: List[str]) -> None:
        payload = {"type": "subscribe", "channels": [{"name": "market", "asset_ids": asset_ids}]}
        await ws.send(json.dumps(payload))

    def _handle_message(self, payload: str) -> None:
        try:
            message = json.loads(payload)
        except json.JSONDecodeError:
            return
        if message.get("channel") != "market":
            return
        data = message.get("data") or {}
        asset_id = str(data.get("asset_id"))
        best_ask = data.get("best_ask")
        ts = data.get("timestamp") or time.time()
        if asset_id and best_ask is not None:
            self.latest_best_ask[asset_id] = {"price": float(best_ask), "timestamp": float(ts)}

    # For tests and offline feeds
    def inject_best_ask(self, asset_id: str, price: float, ts: Optional[float] = None) -> None:
        self.latest_best_ask[asset_id] = {"price": price, "timestamp": ts or time.time()}

    def get_best_ask(self, asset_id: str) -> Optional[float]:
        entry = self.latest_best_ask.get(asset_id)
        if not entry:
            return None
        return float(entry["price"])
