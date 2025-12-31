"""Optional utility to set ERC20 allowances for Polymarket trading.

This script is intentionally inert unless explicitly executed. It only prints
instructions about approving USDC for the settlement contract. Users should
review and customize before running on mainnet.
"""

from __future__ import annotations

import os


def main() -> None:
    print("This helper is a placeholder. Configure your wallet and approve the settlement contract manually.")
    print("Do not run on mainnet without reviewing the code and confirming the spender address.")
    print("Env vars PRIVATE_KEY and RPC_URL should be set if you extend this script.")


if __name__ == "__main__":
    main()
